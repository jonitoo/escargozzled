const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function game() {
    const gradient = { addColorStop() {} };
    const elements = new Map();
    const element = () => ({
        textContent: '', value: '', style: {}, hidden: true,
        classList: { add() {}, remove() {} },
        addEventListener() {}, setAttribute() {}, focus() {},
        replaceChildren() {},
        insertRow: () => ({ appendChild() {} }),
        appendChild(child) { return child; },
        getContext() { return { setTransform() {}, createRadialGradient: () => gradient }; },
    });
    const context = vm.createContext({
        console,
        STERZO_CHALLENGE_TABLE_B64: '',
        atob: (value) => Buffer.from(value, 'base64').toString('binary'),
        Uint8Array,
        performance: { now: () => 100000 },
        window: { innerWidth: 1280, innerHeight: 800, addEventListener() {} },
        document: {
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, element());
                return elements.get(id);
            },
            createElement: element,
        },
        localStorage: { getItem: () => '' },
        setTimeout() {},
        requestAnimationFrame() {},
        fetch: async () => ({ ok: true, json: async () => ({ top: [] }) }),
    });
    vm.runInContext(script, context);
    return (code) => vm.runInContext(code, context);
}

test('sprint target exceeds current/recent power and stays fixed', () => {
    const run = game();
    run('currentWatts = 200; ridingWatts = 200; startChase()');
    assert.equal(run('chase.targetWatts'), 300);
    run('currentWatts = 400; updateChase(100, 100000, 640, 688)');
    assert.equal(run('chase.targetWatts'), 300);
    run('resetChase(); currentWatts = 0; startChase()');
    assert.equal(run('chase.targetWatts'), 175);
    run('resetChase(); currentWatts = 400; startChase()');
    assert.ok(run('chase.targetWatts > 400'));
});

test('normal pace loses ground, sprinting gains ground, target holds it', () => {
    const run = game();
    run('currentWatts = 200; startChase(); updateChase(1000, 100000, 640, 688)');
    assert.ok(run('chase.gap < 0.6'));
    run('currentWatts = chase.targetWatts; chase.gap = 0.6; updateChase(1000, 100000, 640, 688)');
    assert.equal(run('chase.gap'), 0.6);
    run('currentWatts = 400; updateChase(1000, 100000, 640, 688)');
    assert.ok(run('chase.gap > 0.6'));
});

test('being caught costs one life, pushes zombies back and preserves score/level', () => {
    const run = game();
    run('score = 42; levelIdx = 4; startChase(); chase.gap = 0.001; updateChase(100, 100000, 640, 688)');
    assert.equal(run('lives'), 4);
    assert.equal(run('chase.gap'), 0.55);
    assert.equal(run('score'), 42);
    assert.equal(run('levelIdx'), 4);
    assert.equal(run('chase.elapsedMs'), 100);
    run('chase.gap = 0.001; updateChase(100, 100100, 640, 688)');
    assert.equal(run('lives'), 4, 'shared invulnerability prevents another immediate hit');
    run('chase.gap = 0.001; updateChase(100, 102000, 640, 688)');
    assert.equal(run('lives'), 3);
});

test('unchanged normal pace is not sufficient to survive a whole chase unharmed', () => {
    const run = game();
    run('currentWatts = 200; startChase(); for (let i = 0; i < 199; i++) updateChase(100, 100000 + i * 100, 640, 688)');
    assert.ok(run('lives < MAX_LIVES'));
    assert.ok(run('chase !== null'));
});

test('cannon clears every zombie at exactly 20 seconds and normal play resumes', () => {
    const run = game();
    run('currentWatts = 200; startChase(); currentWatts = chase.targetWatts; for (let i = 0; i < 199; i++) updateChase(100, 100000 + i * 100, 640, 688)');
    assert.equal(run('chase.elapsedMs'), 19900);
    assert.equal(run('lives'), 5);
    run('updateChase(100, 120000, 640, 688)');
    assert.equal(run('chase'), null);
    assert.equal(run('cannonMs'), 1500);
    assert.equal(run('chaseCooldownMs'), 18000);
    assert.match(run('chaseTitle.textContent'), /KANONENRETTUNG/);
    run('updateChase(1500, 121500, 640, 688)');
    assert.equal(run('cannonMs'), 0);
    assert.equal(run('chaseHud.hidden'), true);
    assert.equal(run('score'), 0);
    assert.equal(run('levelIdx'), 0);
});

test('random attacks respect rest, require riding, and grow more likely with level', () => {
    const run = game();
    // Fixed random draw lies above level 1's probability but below level 15's.
    run('Math.random = () => 0.004; currentWatts = 200; speed = 20; chaseCooldownMs = 0; updateChase(100, 100000, 640, 688)');
    assert.equal(run('chase'), null);
    run('levelIdx = 14; updateChase(100, 100100, 640, 688)');
    assert.ok(run('chase !== null'));
    run('resetChase(); Math.random = () => 0; updateChase(100, 100200, 640, 688)');
    assert.equal(run('chase'), null, 'initial rest cannot be bypassed');
    run('chaseCooldownMs = 0; currentWatts = 0; updateChase(100, 100300, 640, 688)');
    assert.equal(run('chase'), null, 'no attacks while stopped');
    run('currentWatts = 200; updateChase(100, 100400, 640, 688)');
    assert.ok(run('chase !== null'));
    run('fireCannon(); updateChase(1500, 101900, 640, 688); updateChase(17999, 119899, 640, 688)');
    assert.equal(run('chase'), null, 'post-rescue rest cannot be bypassed');
});

test('restart/end/victory/no lives clear chase and rescue UI', () => {
    const run = game();
    run('startChase(); newGame()');
    assert.equal(run('chase'), null);
    assert.equal(run('chaseCooldownMs'), 15000);
    assert.equal(run('chaseHud.hidden'), true);
    run('startChase(); endGame()');
    assert.equal(run('chase'), null);
    assert.equal(run('chaseHud.hidden'), true);
    for (const condition of ['gameWon = true', 'lives = 0']) {
        run(`newGame(); startChase(); ${condition}; updateChase(100, 100000, 640, 688)`);
        assert.equal(run('chase'), null);
        assert.equal(run('chaseHud.hidden'), true);
    }
});
