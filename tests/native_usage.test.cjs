// Runs only a VM fixture: no browser, native app, network, or real credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../addon/native_usage.js'), 'utf8');
const context = vm.createContext({ Event });
vm.runInContext(source, context);
const { createUsageNotifier, createNativeUsageBridge } = context;

test('usage notifications coalesce revisions and retry failed delivery', async () => {
  let now = 0;
  const calls = [];
  let reject = true;
  const notifier = createUsageNotifier({
    now: () => now,
    changed: () => {},
    invoke: async (command, args) => {
      calls.push([command, args.event]);
      if (reject) throw new Error('fixture failure');
    },
  });
  notifier.update(1);
  await new Promise(setImmediate);
  assert.ok(notifier.error);
  notifier.update(2);
  assert.equal(calls.length, 1);
  reject = false;
  now = 5000;
  await notifier.flush();
  assert.equal(notifier.error, null);
  notifier.update(2);
  await notifier.flush();
  assert.deepEqual(calls, [
    ['plugin:event|emit', 'usage-log-recorded'], ['plugin:event|emit', 'usage-log-recorded'],
  ]);
  notifier.close();
  notifier.update(3);
  assert.equal(calls.length, 2);
});

// Model the committed host tree and useState queues from UsageDashboard
// 4.0.17. Dispatch records updates; commit replaces the rendered tree, leaving
// the DOM attachment on its old alternate just as React may do.
const element = (props) => ({ type: 'fixture', props });
function dashboardFixture(initial = {}) {
  const state = { range: { preset: 'today' }, app: 'all', provider: undefined,
    model: undefined, status: undefined, ...initial };
  const calls = [];
  const group = { isConnected: true };
  const rootState = {};
  const reducer = (state, action) => typeof action === 'function' ? action(state) : action;
  let tree;
  const dispatch = (name, value) => { calls.push([name, value]); state[name] = value; };
  function commit() {
    const selectedApp = state.app;
    const buttons = ['all', 'claude', 'codex', 'mcode'].map((app) => element({
      'aria-pressed': selectedApp === app,
      ...(app === 'all' ? {} : { 'aria-label': app }),
      onClick() {
        dispatch('app', app);
        if (selectedApp !== app) { dispatch('provider', undefined); dispatch('model', undefined); }
      },
      children: app === 'all' ? '全部' : element({ app, size: 16 }),
    }));
    const groupProps = { role: 'group', children: buttons };
    const dateProps = { selection: state.range, triggerLabel: '今天', onApply: (range) => dispatch('range', range) };
    const root = { stateNode: rootState };
    const owner = { type: function UsageDashboard() {}, return: root };
    const body = { return: owner, memoizedProps: { children: [
      element({ children: [element(groupProps), element(dateProps)] }),
    ] } };
    const host = { stateNode: group, memoizedProps: groupProps, return: body };
    const hooks = [{ memoizedState: { unrelated: true } }, ...['range', 'app', 'provider', 'model', 'status'].map((name) => ({
      memoizedState: state[name], queue: { dispatch: (value) => dispatch(name, value), lastRenderedReducer: reducer },
    }))];
    hooks.forEach((hook, i) => { hook.next = hooks[i + 1] || null; });
    owner.memoizedState = hooks[0];
    root.child = owner; owner.child = body; body.child = host;
    rootState.current = root;
    group.__reactFiber$fixture ||= host;
    tree = { root, owner, body, host, hooks, dateProps, buttons };
    return tree;
  }
  commit();
  return { state, calls, group, commit, get tree() { return tree; },
    resolve: () => createNativeUsageBridge().resolve(group),
    nativeClick: (app) => tree.buttons.find((button) => (button.props['aria-label'] || 'all') === app).props.onClick(),
  };
}

test('Droid selects the real app scope even with no provider options or usage rows', () => {
  const f = dashboardFixture({ provider: 'other-provider', model: 'other-model', status: 500 });
  const range = f.state.range;
  const binding = f.resolve();
  assert.equal(binding.selected, false);
  binding.choose();
  assert.deepEqual(f.calls, [['app', 'droid'], ['provider', undefined], ['model', undefined]]);
  assert.equal(f.state.app, 'droid');
  assert.equal(f.state.range, range);
  assert.equal(f.state.status, 500);
  f.commit();
  assert.equal(f.resolve().selected, true);
});

test('Droid and native application buttons apply the same cascading reset', () => {
  const droid = dashboardFixture({ app: 'claude', provider: 'provider-a', model: 'model-a' });
  const native = dashboardFixture({ app: 'claude', provider: 'provider-a', model: 'model-a' });
  droid.resolve().choose();
  native.nativeClick('codex');
  assert.deepEqual(droid.calls.slice(1), native.calls.slice(1));
  assert.deepEqual(droid.calls[0], ['app', 'droid']);
  assert.deepEqual(native.calls[0], ['app', 'codex']);
});

test('clicking active Droid preserves its provider and model just like native buttons', () => {
  const f = dashboardFixture({ app: 'droid', provider: 'droid-provider', model: 'model-a' });
  f.resolve().choose();
  assert.deepEqual(f.calls, [['app', 'droid']]);
  assert.equal(f.state.provider, 'droid-provider');
  assert.equal(f.state.model, 'model-a');
});

test('native All and other app actions leave Droid and clear downstream filters normally', () => {
  for (const app of ['all', 'codex']) {
    const f = dashboardFixture({ app: 'droid', provider: 'droid-provider', model: 'model-a' });
    f.nativeClick(app);
    f.commit();
    assert.equal(f.resolve().selected, false);
    assert.deepEqual(f.calls, [['app', app], ['provider', undefined], ['model', undefined]]);
  }
});

test('changing dates keeps Droid selected and resolves current rather than stale state', () => {
  const f = dashboardFixture();
  f.resolve().choose();
  f.state.provider = 'droid-provider';
  f.state.model = 'model-a';
  f.state.range = { preset: '7d' };
  f.commit();
  f.calls.length = 0;
  assert.equal(f.resolve().selected, true);
  f.resolve().choose();
  assert.deepEqual(f.calls, [['app', 'droid']]);
  assert.equal(f.state.range.preset, '7d');
  assert.equal(f.state.provider, 'droid-provider');
});

test('state updates use dispatch without mutating committed Fiber or hook fields', () => {
  const f = dashboardFixture();
  for (const hook of f.tree.hooks) { if (hook.queue) Object.freeze(hook.queue); Object.freeze(hook); }
  Object.freeze(f.tree.owner);
  f.resolve().choose();
  assert.equal(f.state.app, 'droid');
  assert.equal(f.tree.hooks[2].memoizedState, 'all');
});

test('unrecognized layouts and unrelated date objects fail without dispatching', () => {
  const changes = [
    (f) => { f.tree.dateProps.selection = { preset: 'today' }; },
    (f) => { f.tree.hooks[3].queue = null; },
    (f) => { f.tree.hooks[2].memoizedState = 'codex'; },
    (f) => { f.tree.hooks[5].memoizedState = 'unexpected'; },
    (f) => { f.tree.hooks[5].next = f.tree.hooks[1]; },
    (f) => { f.group.isConnected = false; },
  ];
  for (const change of changes) {
    const f = dashboardFixture();
    change(f);
    assert.equal(f.resolve(), null);
    assert.deepEqual(f.calls, []);
  }
});

function installUI(emptyAppsLabel = null) {
  const listeners = new Map();
  const node = (tag = 'div') => {
    const attrs = new Map();
    return {
      tagName: tag.toUpperCase(), children: [], dataset: {}, label: {},
      isConnected: true,
      setAttribute: (key, value) => attrs.set(key, value),
      getAttribute: (key) => attrs.get(key) ?? null,
      hasAttribute: (key) => attrs.has(key),
      removeAttribute: (key) => attrs.delete(key),
      addEventListener() {},
      remove() {
        if (this.parentElement) this.parentElement.children = this.parentElement.children.filter((el) => el !== this);
      },
      appendChild(child) { this.children.push(child); child.parentElement = this; },
      querySelector(selector) { return selector === '[data-da-nav-label]' ? this.label : null; },
      querySelectorAll: () => [],
    };
  };
  const group = node();
  group.setAttribute('aria-label', emptyAppsLabel);
  const sidebar = {
    querySelectorAll: () => [group], getBoundingClientRect: () => ({ width: 72 }),
  };
  const main = { ...node(), contains: () => true };
  const document = {
    body: node(), head: node(), createElement: node,
    getElementById: () => main,
    querySelectorAll: (selector) => emptyAppsLabel && selector === 'nav' ? [sidebar] : [],
    addEventListener(type, fn) {
      listeners.set(type, [...(listeners.get(type) || []), fn]);
    },
    removeEventListener(type, fn) {
      listeners.set(type, listeners.get(type).filter((value) => value !== fn));
    },
  };
  const window = { addEventListener() {}, removeEventListener() {} };
  const ui = vm.createContext({
    document, window, crypto: { randomUUID: () => 'fixture-instance' },
    Event, setTimeout, clearTimeout, setInterval: () => 1, clearInterval() {},
    MutationObserver: class { observe() {} disconnect() {} },
  });
  vm.runInContext(source, ui);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../addon/inject.js'), 'utf8'), ui);
  return { window, listeners, group };
}

test('injected hook keeps manual sync pending across repeated polls and cleans up', () => {
  const { window, listeners } = installUI();
  const button = {
    disabled: false, textContent: '立即同步', getAttribute: () => null,
    querySelectorAll: () => [], closest: () => null,
  };
  const event = { isTrusted: false, target: { closest: (selector) => selector === 'button' ? button : null } };
  listeners.get('click').forEach((fn) => fn(event));
  assert.equal(window.__ccSwitchDroidHook.poll().syncNow, 1);
  assert.equal(window.__ccSwitchDroidHook.poll().syncNow, 1);
  listeners.get('click').forEach((fn) => fn(event));
  assert.equal(window.__ccSwitchDroidHook.poll().syncNow, 2);
  window.__ccSwitchDroidHook.destroy();
  assert.equal(window.__ccSwitchDroidHook, undefined);
  assert.equal(listeners.get('click').length, 0);
});

test('Droid navigation remains available when all native apps are hidden', () => {
  for (const label of ['Apps', '应用']) {
    const { window, group } = installUI(label);
    assert.equal(group.children.length, 1);
    assert.equal(group.children[0].getAttribute('aria-label'), 'Droid');
    assert.equal(group.children[0].label.hidden, true);
    assert.equal(window.__ccSwitchDroidHook.poll().navAvailable, true);
    window.__ccSwitchDroidHook.destroy();
    assert.equal(group.children.length, 0);
  }
});
