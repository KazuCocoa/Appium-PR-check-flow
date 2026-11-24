const el = id => document.getElementById(id);
const storageKey = 'appium.review.workflows.v1';
let agents = [];
let steps = [];
let saved = [];
let result;
let running = false;

function drawSteps() {
  el('steps').replaceChildren(...steps.map((id, index) => {
    const row = document.createElement('div');
    row.className = 'workflow-step';
    const select = document.createElement('select');
    select.setAttribute('aria-label', 'Agent ' + (index + 1));
    for (const agent of agents) {
      const option = new Option(agent.label, agent.id);
      option.disabled = steps.includes(agent.id) && agent.id !== id;
      select.add(option);
    }
    select.value = id;
    select.onchange = () => { steps[index] = select.value; drawSteps(); };
    row.append(String(index + 1), select);
    function action(text, disabled, perform) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = text;
      button.disabled = disabled;
      button.onclick = () => { perform(); drawSteps(); };
      row.append(button);
    }
    action('Up', index === 0, () => steps.splice(index - 1, 0, ...steps.splice(index, 1)));
    action('Down', index === steps.length - 1, () => steps.splice(index + 1, 0, ...steps.splice(index, 1)));
    action('Remove', false, () => steps.splice(index, 1));
    return row;
  }));
  el('add').disabled = steps.length >= agents.length;
  el('save').disabled = el('run').disabled = !steps.length;
}

function showSaved(selected = '') {
  el('saved').replaceChildren(new Option('New workflow', ''),
    ...saved.map(plan => new Option(plan.name, plan.name)));
  el('saved').value = selected;
}

el('add').onclick = () => {
  const next = agents.find(agent => !steps.includes(agent.id));
  if (next) steps.push(next.id);
  drawSteps();
};
el('saved').onchange = () => {
  const plan = saved.find(item => item.name === el('saved').value);
  steps = plan ? [...plan.steps] : agents.slice(0, 1).map(a => a.id);
  el('name').value = plan?.name || '';
  drawSteps();
};
el('save').onclick = () => {
  if (!el('name').reportValidity()) return;
  const plan = {name: el('name').value, steps: [...steps]};
  const updated = [...saved.filter(item => item.name !== plan.name), plan];
  try {
    localStorage.setItem(storageKey, JSON.stringify(updated));
    saved = updated;
    showSaved(plan.name);
    el('status').textContent = 'Workflow saved in this browser.';
  } catch { el('status').textContent = 'Browser storage unavailable.'; }
};

function inspect(title, value) {
  const details = document.createElement('details');
  const label = document.createElement('summary');
  label.textContent = title;
  const text = document.createElement('pre');
  text.textContent = JSON.stringify(value, null, 2);
  details.append(label, text);
  return details;
}

el('builder').onsubmit = async event => {
  event.preventDefault();
  if (running || !steps.length) return;
  running = true;
  const payload = {name: el('name').value, steps: [...steps], repo: el('repo').value,
    number: Number(el('number').value), provider: el('provider').value};
  const enabled = [...event.currentTarget.elements].filter(c => !c.disabled);
  enabled.forEach(c => { c.disabled = true; });
  el('result').hidden = true;
  el('status').textContent = 'Starting workflow…';
  try {
    const response = await fetch('/api/workflows/run', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    if (!response.ok) throw new Error('Check the repository, PR number and workflow definition.');
    result = await readReview(response, stage => {
      const label = agents.find(a => a.id === stage)?.label || {evidence: 'Collecting evidence', report_writer: 'Writing report'}[stage];
      el('status').textContent = label || stage;
    });
    el('report').innerHTML = result.html;
    el('inspect').replaceChildren(inspect('Shared PR evidence', result.evidence),
      inspect('Shared Skill', result.skill), ...result.stages.map(stage => inspect(stage.agent, stage)));
    el('notes').value = '';
    el('result').hidden = false;
    el('status').textContent = result.status === 'completed' ? 'Workflow complete.' : 'Workflow incomplete.';
  } catch (error) {
    el('status').textContent = error.message;
  } finally {
    running = false;
    enabled.forEach(c => { c.disabled = false; });
  }
};

el('download').onclick = () => {
  const {html, ...record} = result;
  const file = new Blob([JSON.stringify({...record, evaluation: el('notes').value}, null, 2)],
    {type: 'application/json'});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(file);
  link.download = 'workflow-pr-' + record.number + '.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};

async function initialize() {
  const response = await fetch('/api/workflows/agents');
  if (!response.ok) throw new Error('Could not load registered agents.');
  agents = await response.json();
  steps = agents.slice(0, 2).map(a => a.id);
  try {
    const plans = JSON.parse(localStorage.getItem(storageKey) || '[]');
    saved = plans.filter(p => typeof p?.name === 'string' && Array.isArray(p.steps) &&
      p.steps.length && new Set(p.steps).size === p.steps.length &&
      p.steps.every(id => agents.some(a => a.id === id)));
  } catch { saved = []; }
  showSaved();
  drawSteps();
  el('status').textContent = 'Choose agents and a pull request to run.';
}
initialize().catch(error => { el('status').textContent = error.message; });
