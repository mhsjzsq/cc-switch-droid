// Bundled inside renderer.py's per-page install closure.
function createUsageNotifier({ invoke, changed, now = Date.now }) {
  let revision = 0;
  let delivered = 0;
  let pending = false;
  let retryAt = 0;
  let stopped = false;
  let error = null;
  async function flush() {
    if (stopped || pending || revision <= delivered || now() < retryAt) return;
    pending = true;
    const sending = revision;
    try {
      // Same event used by CC Switch's own usage writers and query caches.
      await invoke('plugin:event|emit', { event: 'usage-log-recorded', payload: null });
      delivered = sending;
      error = null;
    } catch (_) {
      error = '用量已写入，但原版统计刷新失败；正在重试，可切换统计范围重新读取。';
      retryAt = now() + 5000;
    } finally {
      pending = false;
      if (!stopped) changed();
    }
  }
  return {
    update(value) {
      if (Number.isSafeInteger(value) && value >= 0) revision = Math.max(revision, value);
      void flush();
    },
    flush,
    get error() { return error; },
    close() { stopped = true; },
  };
}

// Resolve the dashboard's own state setters from the committed React tree.
// Range object identity and the native app group anchor the state layout;
// never guess a hook index, modify Fiber fields, or patch native requests.
function createNativeUsageBridge() {
  function committedPath(element) {
    if (!element?.isConnected) return null;
    const key = Object.keys(element).find((name) => name.startsWith('__reactFiber$'));
    let root = key && element[key];
    if (!root) return null;
    for (let depth = 0; root.return && depth < 150; depth++) root = root.return;
    const current = root.stateNode?.current;
    if (!current) return null;
    // Host attachments can point to an old alternate. Walk the committed tree
    // and retain its actual ancestry, including shared bailout subtrees.
    const stack = [{ fiber: current, parent: null }];
    const visited = new Set();
    while (stack.length && visited.size < 20000) {
      const entry = stack.pop();
      if (visited.has(entry.fiber)) continue;
      visited.add(entry.fiber);
      if (entry.fiber.stateNode === element) {
        const path = [];
        for (let at = entry; at; at = at.parent) path.push(at.fiber);
        return path;
      }
      if (entry.fiber.sibling) stack.push({ fiber: entry.fiber.sibling, parent: entry.parent });
      if (entry.fiber.child) stack.push({ fiber: entry.fiber.child, parent: entry });
    }
    return null;
  }

  function childProps(children) {
    const found = [];
    const stack = [children];
    const visited = new Set();
    while (stack.length && visited.size < 4000) {
      const node = stack.pop();
      if (!node || typeof node !== 'object' || visited.has(node)) continue;
      visited.add(node);
      if (Array.isArray(node)) {
        stack.push(...node);
      } else if (node.props && node.type) {
        found.push(node.props);
        stack.push(node.props.children);
      }
    }
    return stack.length ? [] : found;
  }
  const presets = new Set(['today', '1d', '7d', '14d', '30d', 'all', 'custom']);
  const optionalString = (value) => value === undefined || typeof value === 'string';

  function stateHooks(fiber) {
    const hooks = [];
    const visited = new Set();
    for (let hook = fiber.memoizedState; hook; hook = hook.next) {
      if (visited.has(hook) || hooks.length >= 512) return [];
      visited.add(hook);
      hooks.push(hook);
    }
    return hooks;
  }

  function dashboardBinding(fiber, groupProps) {
    // UsageDashboard returns a host div containing the filter row and body.
    // Inspect its original React element props, including closed menus.
    const elements = childProps(fiber.child?.memoizedProps?.children);
    if (!elements.includes(groupProps)) return null;
    const ranges = elements.filter((props) => presets.has(props.selection?.preset)
      && typeof props.onApply === 'function' && typeof props.triggerLabel === 'string');
    if (ranges.length !== 1) return null;
    const buttons = childProps(groupProps.children).filter((props) => (
      typeof props['aria-pressed'] === 'boolean' && typeof props.onClick === 'function'
    ));
    const apps = buttons.map((props) => ({
      value: props['aria-label']
        ? childProps(props.children).find((child) => typeof child.app === 'string')?.app
        : 'all',
      selected: props['aria-pressed'],
    }));
    if (apps.length < 2 || apps.some((app) => !app.value)
        || apps.filter((app) => app.value === 'all').length !== 1) return null;
    const hooks = stateHooks(fiber);
    const index = hooks.findIndex((hook) => hook.memoizedState === ranges[0].selection);
    if (index < 0) return null;
    // Native order: range, app, provider, model, status. Validate every slot
    // and the rendered selection before using the three existing setters.
    const slots = hooks.slice(index, index + 5);
    if (slots.length !== 5) return null;
    const reducer = slots[0].queue?.lastRenderedReducer;
    if (typeof reducer !== 'function' || slots.some((hook) => (
      typeof hook.queue?.dispatch !== 'function' || hook.queue.lastRenderedReducer !== reducer
    ))) return null;
    const [, app, provider, model, status] = slots;
    const value = app.memoizedState;
    const selected = apps.filter((item) => item.selected);
    const selectionMatches = value === 'droid' ? selected.length === 0
      : selected.length === 1 && selected[0].value === value;
    if (!selectionMatches) return null;
    if (!optionalString(provider.memoizedState) || !optionalString(model.memoizedState)
        || !(status.memoizedState === undefined || Number.isInteger(status.memoizedState))) return null;
    return {
      selected: value === 'droid',
      choose() {
        // Same transition as native changeAppType: preserve date/status,
        // clear provider/model only when changing to another application.
        app.queue.dispatch('droid');
        if (value !== 'droid') {
          provider.queue.dispatch(undefined);
          model.queue.dispatch(undefined);
        }
      },
    };
  }

  function resolve(group) {
    const path = committedPath(group);
    if (!path) return null;
    const groupProps = path[0].memoizedProps;
    if (groupProps?.role !== 'group') return null;
    const matches = path.slice(1).filter((fiber) => typeof fiber.type === 'function')
      .map((fiber) => dashboardBinding(fiber, groupProps)).filter(Boolean);
    return matches.length === 1 ? matches[0] : null;
  }

  return { resolve };
}
