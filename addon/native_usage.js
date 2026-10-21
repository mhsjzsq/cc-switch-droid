// This factory is bundled inside renderer.py's per-page install closure.
// Read native component props and call their existing selection callbacks.
// Never write React state/Fibers, render a component, or open a menu.
function createNativeUsageBridge({ droidProvider, droidLabel }) {
  const allLabel = /^(全部|所有|All|全部供应商|所有供应商|全部供應商|所有供應商|全部来源|所有来源|全部來源|所有來源|All providers|All sources)$/i;
  const isDroidValue = (value) => value === droidProvider || value === 'v:' + droidProvider;

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

  function label(props) {
    const parts = [props.title, props['aria-label']];
    const stack = [props.children];
    for (let count = 0; stack.length && count < 200; count++) {
      const node = stack.pop();
      if (typeof node === 'string' || typeof node === 'number') parts.push(String(node));
      else if (Array.isArray(node)) stack.push(...node);
      else if (node?.props) stack.push(node.props.children);
    }
    return parts.filter((part) => typeof part === 'string').map((part) => part.trim());
  }

  function optionKind(props) {
    if (props.disabled || props['aria-disabled'] === true || props['aria-disabled'] === 'true') return null;
    if (typeof props.value === 'string') {
      if (isDroidValue(props.value)) return 'droid';
      // An encoded provider named "all" is not the clear-filter sentinel.
      return props.value === 'all' ? 'all' : null;
    }
    const labels = label(props);
    if (labels.some((text) => text === droidProvider || text === droidLabel)) return 'droid';
    return labels.some((text) => allLabel.test(text)) ? 'all' : null;
  }

  function valueBinding(props) {
    if (typeof props?.onValueChange !== 'function' || typeof props.value !== 'string') return null;
    const options = childProps(props.children);
    const values = { droid: new Set(), all: new Set() };
    for (const option of options) {
      const kind = optionKind(option);
      if (kind && typeof option.value === 'string') values[kind].add(option.value);
    }
    if (values.all.size !== 1 || values.droid.size > 1) return null;
    const all = [...values.all][0];
    const droid = [...values.droid][0];
    return {
      selected: isDroidValue(props.value),
      available: (wantOn) => !wantOn || droid !== undefined,
      choose: (wantOn) => props.onValueChange(wantOn ? droid : all),
    };
  }

  function actionBinding(props) {
    const actions = { droid: new Set(), all: new Set() };
    for (const option of childProps(props?.children)) {
      const kind = optionKind(option);
      if (kind && typeof option.onSelect === 'function') actions[kind].add(option.onSelect);
    }
    if (actions.all.size !== 1 || actions.droid.size > 1) return null;
    return {
      selected: null, // The trigger's native label provides state for plain items.
      available: (wantOn) => !wantOn || actions.droid.size === 1,
      choose: (wantOn) => {
        const action = [...actions[wantOn ? 'droid' : 'all']][0];
        // Radix onSelect receives a cancellable Event; it is never dispatched.
        action(new Event('droid-hook-select', { cancelable: true }));
      },
    };
  }

  function resolve(trigger, boundary) {
    if (!trigger?.isConnected || !boundary?.contains(trigger)) return null;
    const path = committedPath(trigger);
    if (!path) return null;
    const stop = path.findIndex((fiber) => fiber.stateNode === boundary);
    if (stop < 0) return null;
    let actionFallback = null;
    for (const fiber of path.slice(0, stop)) {
      const props = fiber.memoizedProps;
      if (!props || typeof props !== 'object') continue;
      const direct = valueBinding(props);
      if (direct) return direct;
      // Closed DropdownMenu content is not mounted, but its element props are
      // still children of the owning root. Read them without rendering/opening.
      const groups = childProps(props.children).map(valueBinding).filter(Boolean);
      if (groups.length === 1) return groups[0];
      if (groups.length > 1) return null;
      actionFallback = actionBinding(props) || actionFallback;
    }
    return actionFallback;
  }

  return { resolve };
}
