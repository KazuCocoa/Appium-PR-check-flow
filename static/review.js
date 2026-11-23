const byId = id => document.getElementById(id);
const form = byId('run');
const staged = () => byId('mode').value === 'staged';

function setMode() {
  byId('target').hidden = byId('target').disabled = !staged();
  byId('ask').hidden = byId('question').disabled = staged();
  byId('result').hidden = true;
  byId('status').textContent = staged() ? 'Choose a pull request to begin.' : 'Enter a question to begin.';
}
byId('mode').addEventListener('change', setMode);
setMode();

function showResult(data, isReview) {
  const {html, ...raw} = data;
  // Only the server-rendered Markdown fragment uses HTML. Everything else is text.
  byId('report').innerHTML = html;
  byId('json').textContent = JSON.stringify(raw, null, 2);
  const coverage = isReview ? data.coverage : null;
  const scope = coverage
    ? [`${coverage.complete ? 'Complete' : 'Partial'} patch coverage · ${coverage.files_in_context}/${coverage.files_reported ?? '?'} files`]
    : ['Patch coverage unmeasured'];
  byId('coverage').replaceChildren(...[...scope, 'CI unchecked', 'Tests not executed'].map(label => {
    const span = document.createElement('span');
    span.textContent = label;
    return span;
  }));
  const steps = isReview ? data.trace : data.tools.map(call =>
    `${call.tool} ${JSON.stringify(call.arguments)}${call.error ? ' · ' + call.error : ''}`);
  byId('trace').replaceChildren(...(steps.length ? steps : ['No tools called']).map(label => {
    const item = document.createElement('li');
    item.textContent = label.replace(/^report_writer$/, 'Report Writer');
    return item;
  }));
  byId('result').hidden = false;
}

const stageNames = {
  evidence: 'Collecting PR evidence',
  scout: 'Scout · Identifying areas to investigate',
  reviewer: 'Reviewer · Examining the diff',
  verifier: 'Verifier · Checking proposed findings',
  report_writer: 'Report Writer · Formatting Markdown'
};

async function readReview(response) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let pending = '';
  try {
    while (true) {
      const {value, done} = await reader.read();
      if (done) throw new Error('Review connection closed before a result arrived.');
      const lines = (pending + value).split('\n');
      pending = lines.pop();
      for (const line of lines) {
        const event = JSON.parse(line);
        if (event.error) throw new Error(event.error);
        if (event.result) return event.result;
        if (event.stage) byId('status').textContent = stageNames[event.stage] || event.stage;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const isReview = staged();
  const provider = byId('provider').value;
  const payload = isReview
    ? {repo: byId('repo').value, number: Number(byId('number').value), provider}
    : {question: byId('question').value, provider};
  const enabled = [...form.elements].filter(control => !control.disabled);
  enabled.forEach(control => { control.disabled = true; });
  byId('result').hidden = true;
  byId('status').classList.add('running');
  byId('status').textContent = isReview ? 'Starting review…' : 'Single agent · Processing your question…';
  try {
    const response = await fetch(isReview ? '/api/review/stream' : '/api/ask', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const {detail} = await response.json();
      throw new Error(typeof detail === 'string' ? detail : 'Request failed');
    }
    const data = isReview ? await readReview(response) : await response.json();
    showResult(data, isReview);
    byId('status').textContent = 'Review finished.';
  } catch (error) {
    byId('status').textContent = error.message;
  } finally {
    byId('status').classList.remove('running');
    enabled.forEach(control => { control.disabled = false; });
  }
});
