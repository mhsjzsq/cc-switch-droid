// Add native title tooltips only; React continues to own cell contents and styling.
function createMissingTimingTitles() {
  let owned = new Map();

  function update(cells) {
    const next = new Map();
    cells.forEach(({ element, column, log, nativeTitle }) => {
      if (element.textContent.trim() !== '—') return;
      const title = missingTimingTitle(column, log);
      if (title) next.set(element, { title, nativeTitle });
    });
    owned.forEach((value, element) => {
      if (!next.has(element)) restore(element, value);
    });
    next.forEach((value, element) => {
      if (element.getAttribute('title') !== value.title) element.setAttribute('title', value.title);
    });
    owned = next;
  }

  function restore(element, value) {
    if (element.getAttribute('title') !== value.title) return;
    // React can reuse a cell for a different column or record without changing title.
    const key = Object.keys(element).find((name) => name.startsWith('__reactProps$'));
    const title = key ? element[key]?.title ?? null : value.nativeTitle;
    if (title == null) element.removeAttribute('title');
    else element.setAttribute('title', title);
  }

  return { update, close() { update([]); } };
}

function missingTimingTitle(column, log) {
  // Same number parsing and thresholds as CC Switch 4.0.17 usage/format.ts.
  const number = (value) => {
    const parsed = typeof value === 'string' ? Number.parseFloat(value) : value;
    return typeof parsed === 'number' && Number.isFinite(parsed) ? parsed : null;
  };
  const output = number(log.outputTokens);
  const latency = number(log.latencyMs);
  const firstToken = number(log.firstTokenMs);
  const session = typeof log.dataSource === 'string' && log.dataSource !== '' && log.dataSource !== 'proxy';
  if (column === 'firstToken') {
    if (firstToken != null && firstToken >= 0) return null;
    return session
      ? '首字时间缺失\n这条会话记录没有可用的首字计时数据，无法估算。\n首字是否显示与输出是否达到 200 Token 无关。'
      : '首字时间缺失\n这条请求没有可用的首字计时数据。';
  }
  if (column !== 'speed') return null;
  const reasons = [];
  const minimum = session ? 200 : 100;
  if (output == null) reasons.push('缺少有效的输出 Token 数。');
  else if (output < minimum) reasons.push(`本次输出 ${output.toLocaleString('zh-CN')} Token，不足 ${minimum} Token，未达到显示门槛。`);
  if (session) {
    if (latency == null || latency <= 0) reasons.push('缺少有效的请求耗时，无法估算速度。');
    else if (latency < 1000) reasons.push(`估算总耗时为 ${latency} 毫秒，不足 1 秒，未达到显示门槛。`);
  } else if (latency == null || firstToken == null) {
    reasons.push('缺少请求耗时或首字时间，无法计算生成速度。');
  } else if (latency - firstToken <= 0) {
    reasons.push('请求耗时减去首字时间不大于 0，无法计算生成速度。');
  } else if (latency - firstToken < 100) {
    reasons.push('扣除首字等待后的生成时间不足 100 毫秒，未达到显示门槛。');
  }
  if (!reasons.length) return null;
  return ['速度未显示', ...reasons,
    session ? '会话日志的估算速度包含首字等待；短回复容易受等待时间影响。'
      : '生成速度按输出 Token 数除以扣除首字等待后的生成时间计算。',
  ].join('\n');
}
