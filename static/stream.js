async function readReview(response, onStage) {
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
        if (event.stage) onStage(event.stage);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
