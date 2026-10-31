(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const els = {
    sidebar: $('#sidebar'),
    backdrop: $('#mobile-backdrop'),
    conversationList: $('#conversation-list'),
    conversationTitle: $('#conversation-title'),
    welcome: $('#welcome-screen'),
    messages: $('#message-list'),
    drafts: $('#draft-list'),
    input: $('#message-input'),
    form: $('#chat-form'),
    send: $('#send-button'),
    mic: $('#mic-button'),
    voiceLabel: $('#voice-label'),
    thinking: $('#thinking-row'),
    status: $('#model-status'),
    banner: $('#setup-banner'),
    speech: $('#toggle-speech'),
    memoryPanel: $('#memory-panel'),
    memoryList: $('#memory-list'),
    memoryForm: $('#memory-form'),
    memoryInput: $('#memory-input'),
    toastRegion: $('#toast-region'),
  };

  const state = {
    conversationId: null,
    conversations: [],
    messages: [],
    health: null,
    busy: false,
    speakReplies: localStorage.getItem('friday-speak-replies') === 'true',
    recognition: null,
    mediaRecorder: null,
    recording: false,
    currentAudio: null,
    audioUrl: null,
  };

  async function api(path, options = {}) {
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
    });
    const contentType = response.headers.get('content-type') || '';
    const result = contentType.includes('application/json') ? await response.json() : null;
    if (!response.ok) {
      const detail = result && (result.detail || result.message);
      throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
    }
    return result;
  }

  function showToast(message, kind = '') {
    const toast = document.createElement('div');
    toast.className = `toast ${kind}`.trim();
    toast.textContent = message;
    els.toastRegion.append(toast);
    window.setTimeout(() => toast.remove(), 4400);
  }

  function formatTitle(title) {
    return title && title !== 'New conversation' ? title : 'A little help, whenever you need it.';
  }

  function updateStatus() {
    if (!state.health) return;
    const { model_configured: modelConfigured, assistant_name: assistantName, email_configured: emailConfigured, mcp_connected: mcpConnected, mcp_error: mcpError } = state.health;
    const statusText = els.status.querySelector('span:last-child');
    els.status.classList.remove('offline', 'warning');
    if (modelConfigured) {
      statusText.textContent = 'Ready';
      els.status.title = `${assistantName} is ready`;
    } else {
      els.status.classList.add('warning');
      statusText.textContent = 'Setup needed';
      els.status.title = 'Add an OpenAI-compatible API key in .env to enable chat';
    }

    const notes = [];
    if (!modelConfigured) {
      notes.push('<strong>One quick setup step:</strong> add your model API key to <code>friday/.env</code>, then restart the app. The included <code>.env.example</code> shows the settings.');
    }
    if (!state.health.elevenlabs_stt_configured) {
      notes.push('Set ELEVENLABS_API_KEY to use ElevenLabs transcription; browser voice recognition is used as a fallback where available.');
    }
    if (!state.health.elevenlabs_tts_configured) {
      notes.push('Set ELEVENLABS_VOICE_ID with that key for ElevenLabs spoken replies; browser speech is used as a fallback.');
    }
    if (!emailConfigured) {
      notes.push('Email sending is optional; configure Gmail to send a draft after you review it.');
    }
    if (mcpError) {
      notes.push('The optional n8n MCP connection could not be reached; Friday is running without those extra tools.');
    } else if (state.health.mcp_configured && !mcpConnected) {
      notes.push('The optional n8n MCP server is configured but not connected.');
    }
    els.banner.innerHTML = '';
    if (notes.length) {
      const text = document.createElement('span');
      // Keep configuration notes local and fixed; user/provider values are not interpolated here.
      text.innerHTML = notes.join(' ');
      els.banner.append(text);
      els.banner.classList.remove('hidden');
    } else {
      els.banner.classList.add('hidden');
    }
  }

  function showWelcome(show) {
    els.welcome.classList.toggle('hidden', !show);
    els.messages.classList.toggle('hidden', show);
  }

  function renderMessages() {
    els.messages.replaceChildren();
    state.messages.forEach((message) => {
      const row = document.createElement('article');
      row.className = `message-row ${message.role === 'user' ? 'user' : 'assistant'}`;

      const avatar = document.createElement('div');
      avatar.className = 'message-avatar';
      avatar.setAttribute('aria-hidden', 'true');
      avatar.textContent = message.role === 'user' ? 'YOU' : 'F';

      const content = document.createElement('div');
      content.className = 'message-content';
      content.textContent = message.content || '';
      row.append(avatar, content);
      els.messages.append(row);
    });
    showWelcome(state.messages.length === 0);
    if (state.messages.length) {
      requestAnimationFrame(() => {
        els.messages.scrollIntoView({ block: 'end', behavior: 'smooth' });
      });
    }
  }

  function renderConversations() {
    els.conversationList.replaceChildren();
    if (!state.conversations.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-history';
      empty.textContent = 'Your conversations will appear here.';
      els.conversationList.append(empty);
      return;
    }
    state.conversations.forEach((conversation) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `conversation-item ${conversation.id === state.conversationId ? 'active' : ''}`;
      button.title = conversation.title;
      const glyph = document.createElement('span');
      glyph.className = 'conversation-glyph';
      glyph.setAttribute('aria-hidden', 'true');
      glyph.textContent = '◷';
      const title = document.createElement('span');
      title.className = 'conversation-title';
      title.textContent = conversation.title || 'New conversation';
      button.append(glyph, title);
      button.addEventListener('click', () => loadConversation(conversation.id));
      els.conversationList.append(button);
    });
  }

  function draftField(label, value) {
    const line = document.createElement('div');
    line.className = 'draft-line';
    const key = document.createElement('strong');
    key.textContent = label;
    const text = document.createElement('span');
    text.textContent = value || '—';
    line.append(key, text);
    return line;
  }

  function renderDrafts(drafts) {
    els.drafts.replaceChildren();
    drafts.forEach((draft) => {
      const card = document.createElement('section');
      card.className = 'email-draft';

      const header = document.createElement('div');
      header.className = 'draft-header';
      const label = document.createElement('div');
      label.className = 'draft-label';
      label.textContent = '✉  Email draft';
      const status = document.createElement('span');
      status.className = 'draft-state';
      status.textContent = draft.status === 'sent' ? 'Sent' : draft.status === 'sending' ? 'Sending…' : 'Not sent — review first';
      header.append(label, status);

      const body = document.createElement('div');
      body.className = 'draft-body';
      body.append(draftField('To', draft.to_email));
      if (draft.cc_email) body.append(draftField('Cc', draft.cc_email));
      body.append(draftField('Subject', draft.subject));
      const text = document.createElement('div');
      text.className = 'draft-text';
      text.textContent = draft.body;
      body.append(text);

      const actions = document.createElement('div');
      actions.className = 'draft-actions';
      if (draft.status === 'draft') {
        const discard = document.createElement('button');
        discard.className = 'draft-button';
        discard.type = 'button';
        discard.textContent = 'Discard';
        discard.addEventListener('click', async () => {
          try {
            await api(`/api/drafts/${encodeURIComponent(draft.id)}/discard`, { method: 'POST' });
            await refreshDrafts();
            showToast('Draft discarded.');
          } catch (error) { showToast(error.message, 'error'); }
        });

        const send = document.createElement('button');
        send.className = 'draft-button send';
        send.type = 'button';
        send.textContent = 'Review & send';
        send.addEventListener('click', async () => {
          const confirmed = window.confirm(`Send this email to ${draft.to_email}?\n\nSubject: ${draft.subject}\n\nThis action cannot be undone.`);
          if (!confirmed) return;
          send.disabled = true;
          try {
            const result = await api(`/api/drafts/${encodeURIComponent(draft.id)}/send`, {
              method: 'POST', body: JSON.stringify({ confirm: true }),
            });
            showToast(result.message || 'Email sent.');
            await refreshDrafts();
          } catch (error) {
            send.disabled = false;
            showToast(error.message, 'error');
          }
        });
        actions.append(discard, send);
      } else if (draft.status === 'sent') {
        const sent = document.createElement('span');
        sent.className = 'draft-sent';
        sent.textContent = `✓ Sent to ${draft.to_email}`;
        actions.append(sent);
      }
      card.append(header, body, actions);
      els.drafts.append(card);
    });
  }

  async function refreshDrafts() {
    if (!state.conversationId) return;
    const drafts = await api(`/api/drafts?conversation_id=${encodeURIComponent(state.conversationId)}`);
    renderDrafts(drafts);
  }

  async function refreshConversationList() {
    state.conversations = await api('/api/conversations');
    renderConversations();
  }

  async function loadConversation(conversationId) {
    try {
      const conversation = await api(`/api/conversations/${encodeURIComponent(conversationId)}`);
      state.conversationId = conversation.id;
      state.messages = conversation.messages || [];
      els.conversationTitle.textContent = formatTitle(conversation.title);
      renderMessages();
      await refreshDrafts();
      await refreshConversationList();
      closeSidebar();
    } catch (error) {
      showToast(error.message, 'error');
    }
  }

  async function startConversation() {
    try {
      const conversation = await api('/api/conversations', {
        method: 'POST', body: JSON.stringify({}),
      });
      state.conversationId = conversation.id;
      state.messages = [];
      els.conversationTitle.textContent = formatTitle(conversation.title);
      renderMessages();
      renderDrafts([]);
      await refreshConversationList();
      els.input.focus();
      closeSidebar();
    } catch (error) {
      showToast(error.message, 'error');
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    els.send.disabled = busy || !els.input.value.trim();
    els.input.disabled = busy;
    els.thinking.classList.toggle('hidden', !busy);
    if (busy) els.thinking.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  async function speak(text) {
    if (!state.speakReplies || !text) return;
    if (state.currentAudio) {
      state.currentAudio.pause();
      state.currentAudio = null;
    }
    if (state.audioUrl) {
      URL.revokeObjectURL(state.audioUrl);
      state.audioUrl = null;
    }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();

    if (state.health?.elevenlabs_tts_configured) {
      try {
        const response = await fetch('/api/speech', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text.slice(0, 5000) }),
        });
        if (!response.ok) {
          const errorBody = await response.json().catch(() => null);
          throw new Error(errorBody?.detail || `ElevenLabs speech failed (${response.status}).`);
        }
        const audioBlob = await response.blob();
        if (!audioBlob.size) throw new Error('ElevenLabs returned empty audio.');
        if (!state.speakReplies) return;
        state.audioUrl = URL.createObjectURL(audioBlob);
        const player = new Audio(state.audioUrl);
        state.currentAudio = player;
        player.onended = () => {
          if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
          state.audioUrl = null;
          state.currentAudio = null;
        };
        await player.play();
        return;
      } catch (error) {
        showToast(`${error.message} Using browser speech instead.`, 'error');
      }
    }

    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = document.documentElement.lang || navigator.language || 'en-US';
      utterance.rate = 1;
      window.speechSynthesis.speak(utterance);
    }
  }

  async function sendMessage(text) {
    const clean = (text || '').trim();
    if (!clean || state.busy) return;
    if (!state.conversationId) {
      const created = await api('/api/conversations', { method: 'POST', body: JSON.stringify({}) });
      state.conversationId = created.id;
    }

    state.messages.push({ role: 'user', content: clean });
    renderMessages();
    els.input.value = '';
    resizeInput();
    setBusy(true);
    try {
      const response = await api('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ conversation_id: state.conversationId, message: clean }),
      });
      state.messages.push(response.assistant_message);
      els.conversationTitle.textContent = formatTitle(response.conversation?.title);
      renderMessages();
      renderDrafts(response.drafts || []);
      await refreshConversationList();
      speak(response.assistant_message.content);
    } catch (error) {
      // The backend persists a chat only after a successful model response.
      const index = state.messages.findIndex((message, i) => i === state.messages.length - 1 && message.role === 'user' && message.content === clean);
      if (index >= 0) state.messages.splice(index, 1);
      renderMessages();
      showToast(error.message, 'error');
      try { await refreshDrafts(); } catch { /* A draft may not exist for this conversation yet. */ }
      if (state.health && !state.health.model_configured) {
        els.banner.classList.remove('hidden');
      }
    } finally {
      setBusy(false);
      els.input.focus();
    }
  }

  function resizeInput() {
    els.input.style.height = 'auto';
    els.input.style.height = `${Math.min(els.input.scrollHeight, 180)}px`;
    els.send.disabled = state.busy || !els.input.value.trim();
  }

  function closeSidebar() {
    els.sidebar.classList.remove('open');
    els.backdrop.classList.remove('open');
  }

  async function loadMemories() {
    try {
      const memories = await api('/api/memories');
      els.memoryList.replaceChildren();
      if (!memories.length) {
        const empty = document.createElement('div');
        empty.className = 'empty-memories';
        empty.textContent = 'No saved memories yet. Ask Friday to remember something, or add a note above.';
        els.memoryList.append(empty);
        return;
      }
      memories.forEach((memory) => {
        const item = document.createElement('article');
        item.className = 'memory-item';
        const copy = document.createElement('div');
        copy.style.flex = '1';
        const text = document.createElement('p');
        text.textContent = memory.content;
        const date = document.createElement('small');
        date.textContent = new Date(memory.updated_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
        copy.append(text, date);
        const remove = document.createElement('button');
        remove.className = 'memory-delete';
        remove.type = 'button';
        remove.setAttribute('aria-label', 'Delete saved memory');
        remove.title = 'Delete this memory';
        remove.textContent = '×';
        remove.addEventListener('click', async () => {
          try {
            await api(`/api/memories/${memory.id}`, { method: 'DELETE' });
            await loadMemories();
            showToast('Memory deleted.');
          } catch (error) { showToast(error.message, 'error'); }
        });
        item.append(copy, remove);
        els.memoryList.append(item);
      });
    } catch (error) {
      els.memoryList.textContent = error.message;
    }
  }

  function openMemoryPanel() {
    els.memoryPanel.classList.add('open');
    els.memoryPanel.setAttribute('aria-hidden', 'false');
    loadMemories();
    els.memoryInput.focus();
  }

  function closeMemoryPanel() {
    els.memoryPanel.classList.remove('open');
    els.memoryPanel.setAttribute('aria-hidden', 'true');
  }

  function setRecordingUI(active, label = 'Listening…') {
    state.recording = active;
    els.mic.classList.toggle('listening', active);
    els.mic.setAttribute('aria-label', active ? 'Stop recording' : 'Speak your message');
    els.voiceLabel.textContent = label;
    els.voiceLabel.classList.toggle('hidden', !active);
  }

  async function transcribeRecording(blob) {
    if (!blob.size) {
      showToast('No audio was recorded. Try again.', 'error');
      return;
    }
    if (blob.size > 20 * 1024 * 1024) {
      showToast('That recording is too large. Keep it under 20 MB.', 'error');
      return;
    }
    const contentType = blob.type || 'audio/webm';
    const extension = contentType.includes('mp4') ? 'mp4' : contentType.includes('ogg') ? 'ogg' : contentType.includes('wav') ? 'wav' : 'webm';
    const form = new FormData();
    form.append('file', blob, `friday-recording.${extension}`);
    els.mic.disabled = true;
    els.voiceLabel.textContent = 'Transcribing with ElevenLabs…';
    els.voiceLabel.classList.remove('hidden');
    try {
      const result = await api('/api/transcribe', { method: 'POST', body: form });
      const transcript = (result.text || '').trim();
      if (!transcript) {
        showToast('ElevenLabs did not detect any words. Try speaking a little closer to the microphone.', 'error');
        return;
      }
      els.input.value = transcript;
      resizeInput();
      await sendMessage(transcript);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      els.mic.disabled = false;
      els.voiceLabel.classList.add('hidden');
    }
  }

  async function startElevenLabsRecording() {
    if (state.recording) {
      state.mediaRecorder?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const supportedTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
      const mimeType = supportedTypes.find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      const chunks = [];
      state.mediaRecorder = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunks.push(event.data);
      };
      recorder.onerror = () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecordingUI(false);
        showToast('Microphone recording failed. Check browser permissions and try again.', 'error');
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        state.mediaRecorder = null;
        setRecordingUI(false);
        await transcribeRecording(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
      };
      setRecordingUI(true);
      recorder.start();
    } catch (error) {
      showToast('Friday could not access your microphone. Allow microphone access in your browser and try again.', 'error');
    }
  }

  function setupBrowserSpeechRecognition(SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.lang = navigator.language || 'en-US';
    recognition.continuous = false;
    recognition.interimResults = true;
    state.recognition = recognition;
    let transcript = '';

    recognition.onstart = () => {
      transcript = '';
      setRecordingUI(true);
    };
    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const spoken = event.results[i][0].transcript;
        if (event.results[i].isFinal) transcript += `${spoken} `;
        else interim += spoken;
      }
      els.input.value = `${transcript}${interim}`.trimStart();
      resizeInput();
    };
    recognition.onerror = (event) => {
      if (event.error !== 'no-speech' && event.error !== 'aborted') showToast(`Voice input: ${event.error}`, 'error');
    };
    recognition.onend = () => {
      setRecordingUI(false);
      const finalText = transcript.trim();
      if (finalText) sendMessage(finalText);
    };
    els.mic.addEventListener('click', () => {
      if (state.recording) recognition.stop();
      else {
        try { recognition.start(); }
        catch { showToast('Voice input is already starting. Try again in a moment.', 'error'); }
      }
    });
  }

  function setupVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const canRecordAudio = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
    if (state.health?.elevenlabs_stt_configured && canRecordAudio) {
      els.mic.title = 'Record a message and transcribe it with ElevenLabs';
      els.mic.addEventListener('click', startElevenLabsRecording);
      return;
    }
    if (SpeechRecognition) {
      els.mic.title = 'Speak your message using browser voice recognition';
      setupBrowserSpeechRecognition(SpeechRecognition);
      return;
    }
    els.mic.disabled = true;
    els.mic.title = 'Set up ElevenLabs voice transcription or use a browser with speech recognition.';
  }

  async function initialize() {
    try {
      state.health = await api('/api/health');
      updateStatus();
    } catch (error) {
      els.status.classList.add('offline');
      els.status.querySelector('span:last-child').textContent = 'App unavailable';
      els.banner.textContent = `Friday could not load its setup status: ${error.message}`;
      els.banner.classList.remove('hidden');
    }
    els.speech.setAttribute('aria-pressed', String(state.speakReplies));
    els.speech.querySelector('.speech-label').textContent = state.speakReplies ? 'Voice on' : 'Voice off';
    setupVoiceInput();

    try {
      await refreshConversationList();
      if (state.conversations.length) await loadConversation(state.conversations[0].id);
      else await startConversation();
    } catch (error) {
      showToast(error.message, 'error');
    }
  }

  els.form.addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage(els.input.value);
  });
  els.input.addEventListener('input', resizeInput);
  els.input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      els.form.requestSubmit();
    }
  });
  $('#new-chat').addEventListener('click', startConversation);
  $('#delete-chat').addEventListener('click', async () => {
    if (!state.conversationId) return;
    const current = state.conversations.find((conversation) => conversation.id === state.conversationId);
    const label = current?.title || 'this conversation';
    if (!window.confirm(`Delete “${label}” and its email drafts? This cannot be undone.`)) return;
    try {
      await api(`/api/conversations/${encodeURIComponent(state.conversationId)}`, { method: 'DELETE' });
      state.conversationId = null;
      state.messages = [];
      renderDrafts([]);
      await startConversation();
      showToast('Conversation deleted.');
    } catch (error) { showToast(error.message, 'error'); }
  });
  $('#mobile-menu').addEventListener('click', () => {
    els.sidebar.classList.add('open');
    els.backdrop.classList.add('open');
  });
  $('#sidebar-close').addEventListener('click', closeSidebar);
  els.backdrop.addEventListener('click', closeSidebar);
  $('#open-memories').addEventListener('click', openMemoryPanel);
  $('#close-memories').addEventListener('click', closeMemoryPanel);

  document.querySelectorAll('.suggestion-card').forEach((button) => {
    button.addEventListener('click', () => sendMessage(button.dataset.prompt || ''));
  });

  els.speech.addEventListener('click', () => {
    state.speakReplies = !state.speakReplies;
    localStorage.setItem('friday-speak-replies', String(state.speakReplies));
    els.speech.setAttribute('aria-pressed', String(state.speakReplies));
    els.speech.querySelector('.speech-label').textContent = state.speakReplies ? 'Voice on' : 'Voice off';
    if (!state.speakReplies) {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      if (state.currentAudio) {
        state.currentAudio.pause();
        state.currentAudio = null;
      }
      if (state.audioUrl) {
        URL.revokeObjectURL(state.audioUrl);
        state.audioUrl = null;
      }
    }
  });

  els.memoryForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const memory = els.memoryInput.value.trim();
    if (!memory) return;
    const button = els.memoryForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api('/api/memories', { method: 'POST', body: JSON.stringify({ memory }) });
      els.memoryInput.value = '';
      await loadMemories();
      showToast('Memory saved.');
    } catch (error) { showToast(error.message, 'error'); }
    finally { button.disabled = false; }
  });

  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      startConversation();
    }
    if (event.key === 'Escape') {
      closeMemoryPanel();
      closeSidebar();
    }
  });

  initialize();
})();
