const state = {
  authToken: localStorage.getItem('live_editor_auth_token') || '',
  user: null,
  color: localStorage.getItem('live_editor_color') || null,
  socket: null,
  socketReady: false,
  joined: false,
  clientId: `client_${Math.random().toString(36).slice(2, 11)}`,
  palette: [],
  claimedColors: {},
  files: [],
  tabLimit: 6,
  activeFileId: null,
  lineAuthors: {},
  activeUsers: [],
  students: [],
  editableOwnerIds: new Set(),
  globalEditor: false,
  editor: null,
  isRemoteChange: false,
  typingTimeout: null,
  typingUsers: new Set(),
  remoteCursors: new Map(),
  lineTypingTimeouts: new Map(),
  chatHistory: [],
  currentChatTab: 'group',
  activeDmAccountId: null,
  unreadCount: 0,
};

const $ = (id) => document.getElementById(id);
const body = document.body;

const elements = {
  btnThemeToggle: $('btnThemeToggle'),
  iconMoon: $('iconMoon'),
  iconSun: $('iconSun'),
  btnFontInc: $('btnFontInc'),
  btnFontDec: $('btnFontDec'),
  lblFontSize: $('lblFontSize'),
  lanBadge: $('lanBadge'),
  lanIpText: $('lanIpText'),
  btnShowQr: $('btnShowQr'),
  dlgQr: $('dlgQr'),
  imgQrCode: $('imgQrCode'),
  txtLanUrl: $('txtLanUrl'),
  btnCopyLanUrl: $('btnCopyLanUrl'),
  btnCloseQr: $('btnCloseQr'),
  dlgLogin: $('dlgLogin'),
  loginRoleSelection: $('loginRoleSelection'),
  loginSubtitle: $('loginSubtitle'),
  btnChooseAdmin: $('btnChooseAdmin'),
  btnChooseStudent: $('btnChooseStudent'),
  frmAdminLogin: $('frmAdminLogin'),
  frmStudentLogin: $('frmStudentLogin'),
  btnBackFromAdmin: $('btnBackFromAdmin'),
  btnBackFromStudent: $('btnBackFromStudent'),
  txtAdminPassword: $('txtAdminPassword'),
  txtStudentIdLogin: $('txtStudentIdLogin'),
  txtStudentDobLogin: $('txtStudentDobLogin'),
  txtStudentPassword: $('txtStudentPassword'),
  loginColorSection: $('loginColorSection'),
  colorGrid: $('colorGrid'),
  loginMessage: $('loginMessage'),
  userProfileBadge: $('userProfileBadge'),
  myAvatar: $('myAvatar'),
  myUsername: $('myUsername'),
  myAdminCrown: $('myAdminCrown'),
  btnLogout: $('btnLogout'),
  presenceBar: $('presenceBar'),
  avatarGroup: $('avatarGroup'),
  typingBanner: $('typingBanner'),
  typingBannerText: $('typingBannerText'),
  wsStatus: $('wsStatus'),
  wsStatusText: $('wsStatusText'),
  fileTabs: $('fileTabs'),
  btnAddFile: $('btnAddFile'),
  tabCountLabel: $('tabCountLabel'),
  currentFileTag: $('currentFileTag'),
  currentLanguageBadge: $('currentLanguageBadge'),
  btnRunCode: $('btnRunCode'),
  runButtonLabel: $('runButtonLabel'),
  btnCopyCode: $('btnCopyCode'),
  btnSaveSnapshot: $('btnSaveSnapshot'),
  outputDrawer: $('outputDrawer'),
  programInput: $('programInput'),
  btnClearProgramInput: $('btnClearProgramInput'),
  consoleOutput: $('consoleOutput'),
  execTimeTag: $('execTimeTag'),
  btnClearOutput: $('btnClearOutput'),
  btnToggleOutput: $('btnToggleOutput'),
  iconDrawerChevron: $('iconDrawerChevron'),
  btnSettings: $('btnSettings'),
  settingsButtonLabel: $('settingsButtonLabel'),
  dlgAdminSettings: $('dlgAdminSettings'),
  btnCloseAdminSettings: $('btnCloseAdminSettings'),
  txtAdminDisplayName: $('txtAdminDisplayName'),
  btnSaveAdminName: $('btnSaveAdminName'),
  adminNameMessage: $('adminNameMessage'),
  frmAddStudent: $('frmAddStudent'),
  txtNewStudentName: $('txtNewStudentName'),
  txtNewStudentId: $('txtNewStudentId'),
  txtNewStudentDob: $('txtNewStudentDob'),
  txtNewStudentInfo: $('txtNewStudentInfo'),
  studentRecordMessage: $('studentRecordMessage'),
  studentRecordsList: $('studentRecordsList'),
  numTabLimit: $('numTabLimit'),
  btnSaveTabLimit: $('btnSaveTabLimit'),
  tabLimitMessage: $('tabLimitMessage'),
  adminGlobalAccessList: $('adminGlobalAccessList'),
  dlgStudentSettings: $('dlgStudentSettings'),
  btnCloseStudentSettings: $('btnCloseStudentSettings'),
  studentCodeAccessList: $('studentCodeAccessList'),
  dlgNewFile: $('dlgNewFile'),
  btnCloseNewFile: $('btnCloseNewFile'),
  frmNewFile: $('frmNewFile'),
  txtNewFileName: $('txtNewFileName'),
  selNewFileLanguage: $('selNewFileLanguage'),
  newFileMessage: $('newFileMessage'),
  dlgSnapshots: $('dlgSnapshots'),
  btnSnapshots: $('btnSnapshots'),
  btnCloseSnapshots: $('btnCloseSnapshots'),
  snapshotsList: $('snapshotsList'),
  toastContainer: $('toastContainer'),
  chatSidebar: $('chatSidebar'),
  chatResizeHandle: $('chatResizeHandle'),
  btnToggleChatBar: $('btnToggleChatBar'),
  btnCollapseChat: $('btnCollapseChat'),
  btnMinimizeChat: $('btnMinimizeChat'),
  chatUnreadBadge: $('chatUnreadBadge'),
  tabGroupChat: $('tabGroupChat'),
  tabPrivateChat: $('tabPrivateChat'),
  dmSubSidebar: $('dmSubSidebar'),
  dmConversationsList: $('dmConversationsList'),
  btnNewDm: $('btnNewDm'),
  dmSelectorBox: $('dmSelectorBox'),
  selDmRecipient: $('selDmRecipient'),
  dmConversationHeader: $('dmConversationHeader'),
  btnBackToDmList: $('btnBackToDmList'),
  dmActiveAvatar: $('dmActiveAvatar'),
  dmActiveName: $('dmActiveName'),
  dmActiveStatus: $('dmActiveStatus'),
  chatMessagesContainer: $('chatMessagesContainer'),
  frmChat: $('frmChat'),
  txtChatMessage: $('txtChatMessage'),
  btnAttachFile: $('btnAttachFile'),
};

let currentFontSize = 15;
let isChatCollapsed = localStorage.getItem('chat_collapsed') === 'true';
let isChatMinimized = localStorage.getItem('chat_minimized') === 'true';

document.addEventListener('DOMContentLoaded', async () => {
  lucide.createIcons();
  initializeTheme();
  initializeEditor();
  bindInterfaceEvents();
  restoreChatLayout();
  syncChatView();
  initializeWebSocket();
  await fetchAppInfo();
  await restoreSession();
});

function initializeTheme() {
  setTheme(localStorage.getItem('editor_theme') || 'dark');
}

function setTheme(theme) {
  body.setAttribute('data-theme', theme);
  localStorage.setItem('editor_theme', theme);
  const dark = theme === 'dark';
  elements.iconMoon.style.display = dark ? 'block' : 'none';
  elements.iconSun.style.display = dark ? 'none' : 'block';
  if (state.editor) {
    state.editor.setOption('theme', dark ? 'dracula' : 'eclipse');
  }
}

function setFontSize(size) {
  currentFontSize = Math.min(Math.max(size, 12), 28);
  elements.lblFontSize.textContent = `${currentFontSize}px`;
  const editorElement = document.querySelector('.CodeMirror');
  if (editorElement) editorElement.style.fontSize = `${currentFontSize}px`;
  state.editor?.refresh();
}

function initializeEditor() {
  state.editor = CodeMirror.fromTextArea($('codeEditor'), {
    mode: 'python',
    theme: body.getAttribute('data-theme') === 'dark' ? 'dracula' : 'eclipse',
    lineNumbers: true,
    matchBrackets: true,
    autoCloseBrackets: true,
    styleActiveLine: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    extraKeys: {
      Tab(cm) {
        if (cm.somethingSelected()) cm.indentSelection('add');
        else cm.replaceSelection('    ', 'end');
      },
    },
  });
  setFontSize(15);

  const creatorTooltip = document.createElement('div');
  creatorTooltip.className = 'creator-tooltip';
  creatorTooltip.style.display = 'none';
  document.body.appendChild(creatorTooltip);

  state.editor.on('beforeChange', (cm, change) => {
    if (state.isRemoteChange || change.origin === 'remote') return;
    if (!state.joined || !state.activeFileId) {
      change.cancel();
      showToast('Please log in before editing.', 'error');
      return;
    }

    const blockedLine = firstBlockedLine(change.from.line, change.to.line);
    if (blockedLine === null) return;

    const isEnterOnly = (
      change.from.line === change.to.line
      && change.from.ch === change.to.ch
      && Array.isArray(change.text)
      && change.text.length > 1
      && change.text.every((part) => part.trim() === '')
    );

    change.cancel();
    if (isEnterOnly) {
      sendWsMessage({
        type: 'insert_lines',
        file_id: state.activeFileId,
        after_line: blockedLine,
        count: change.text.length - 1,
      });
      return;
    }
    showToast('This line is read-only. Press Enter to create a line beneath it.', 'error');
  });

  state.editor.on('change', (cm, change) => {
    if (state.isRemoteChange || change.origin === 'remote') return;
    const activeFile = getActiveFile();
    if (!activeFile) return;

    let currentChange = change;
    while (currentChange) {
      sendWsMessage({
        type: 'code_delta',
        file_id: activeFile.id,
        from: currentChange.from,
        to: currentChange.to,
        text: currentChange.text,
        revision: activeFile.revision,
      });
      currentChange = currentChange.next;
    }
    activeFile.code = cm.getValue();
    handleLocalTyping();
  });

  state.editor.on('cursorActivity', (cm) => {
    if (state.isRemoteChange || !state.joined || !state.activeFileId) return;
    sendWsMessage({
      type: 'cursor_change',
      file_id: state.activeFileId,
      cursor: cm.getCursor(),
    });
  });

  state.editor.getWrapperElement().addEventListener('mousemove', (event) => {
    const coordinates = state.editor.coordsChar({ left: event.clientX, top: event.clientY });
    const info = getActiveLineAuthors()[String(coordinates.line)];
    if (!info?.author) {
      creatorTooltip.style.display = 'none';
      return;
    }
    creatorTooltip.replaceChildren();
    creatorTooltip.append('Created by: ');
    const owner = document.createElement('strong');
    owner.textContent = `${info.author}${info.account_id === 'admin' ? ' ♛' : ''}`;
    owner.style.color = safeColor(info.color);
    creatorTooltip.appendChild(owner);
    creatorTooltip.style.left = `${event.clientX + 14}px`;
    creatorTooltip.style.top = `${event.clientY + 14}px`;
    creatorTooltip.style.display = 'block';
  });

  state.editor.getWrapperElement().addEventListener('mouseleave', () => {
    creatorTooltip.style.display = 'none';
  });
}

function firstBlockedLine(startLine, endLine) {
  if (state.user?.role === 'admin' || state.globalEditor) return null;
  const authors = getActiveLineAuthors();
  for (let line = startLine; line <= endLine; line += 1) {
    const lineText = state.editor.getLine(line) || '';
    if (!lineText.trim()) continue;
    const ownerId = authors[String(line)]?.account_id;
    if (!ownerId || ownerId === state.user?.account_id) continue;
    if (state.editableOwnerIds.has(ownerId)) continue;
    return line;
  }
  return null;
}

function handleLocalTyping() {
  const line = state.editor.getCursor().line;
  sendWsMessage({ type: 'typing', is_typing: true });
  sendWsMessage({
    type: 'typing_line',
    file_id: state.activeFileId,
    line,
    is_typing: true,
  });
  clearTimeout(state.typingTimeout);
  state.typingTimeout = setTimeout(() => {
    sendWsMessage({ type: 'typing', is_typing: false });
    sendWsMessage({
      type: 'typing_line',
      file_id: state.activeFileId,
      line,
      is_typing: false,
    });
  }, 1200);
}

async function fetchAppInfo() {
  try {
    const response = await fetch('/api/info');
    const info = await response.json();
    elements.lanIpText.textContent = `${info.ip}:${info.port}`;
    elements.txtLanUrl.value = info.lan_url;
    elements.imgQrCode.src = info.qr_code;
    state.palette = info.palette || [];
    state.claimedColors = info.claimed_colors || {};
    state.activeUsers = info.active_users || [];
    chooseAvailableColor();
    renderColorGrid();
    renderPresence();
  } catch {
    elements.lanIpText.textContent = 'Offline / Localhost';
  }
}

async function restoreSession() {
  if (!state.authToken) {
    showLoginDialog();
    return;
  }
  try {
    const response = await authorizedFetch('/api/auth/me');
    if (!response.ok) throw new Error('Session expired');
    const data = await response.json();
    state.user = data.user;
    chooseAvailableColor();
    updateSignedInUI();
    tryJoinSocket();
  } catch {
    clearAuthentication();
    showLoginDialog();
  }
}

function showLoginDialog() {
  resetLoginChoice();
  if (!elements.dlgLogin.open) elements.dlgLogin.showModal();
}

function resetLoginChoice() {
  elements.loginRoleSelection.style.display = 'grid';
  elements.frmAdminLogin.style.display = 'none';
  elements.frmStudentLogin.style.display = 'none';
  elements.loginColorSection.style.display = 'none';
  elements.loginSubtitle.textContent = 'Choose how you want to sign in.';
  setMessage(elements.loginMessage, '');
}

function selectLoginRole(role) {
  elements.loginRoleSelection.style.display = 'none';
  elements.frmAdminLogin.style.display = role === 'admin' ? 'block' : 'none';
  elements.frmStudentLogin.style.display = role === 'student' ? 'block' : 'none';
  elements.loginColorSection.style.display = 'block';
  elements.loginSubtitle.textContent = role === 'admin'
    ? 'Enter the Admin password and choose a cursor color.'
    : 'Enter your saved student details. Your name will be loaded automatically.';
  setMessage(elements.loginMessage, '');
  renderColorGrid();
  if (role === 'admin') elements.txtAdminPassword.focus();
  else elements.txtStudentIdLogin.focus();
}

function chooseAvailableColor() {
  const available = state.palette.find(
    (color) => !state.claimedColors[color] || state.claimedColors[color] === state.user?.username,
  );
  if (!state.color || !state.palette.includes(state.color) || (
    state.claimedColors[state.color]
    && state.claimedColors[state.color] !== state.user?.username
  )) {
    state.color = available || state.palette[0] || '#2196F3';
  }
}

function renderColorGrid() {
  elements.colorGrid.replaceChildren();
  state.palette.forEach((color) => {
    const claimedBy = state.claimedColors[color];
    const claimed = Boolean(claimedBy && claimedBy !== state.user?.username);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `color-option${claimed ? ' claimed' : ''}${state.color === color ? ' selected' : ''}`;
    button.style.backgroundColor = color;
    button.title = claimed ? `Used by ${claimedBy}` : `Choose ${color}`;
    button.disabled = claimed;
    button.setAttribute('aria-label', button.title);
    button.addEventListener('click', () => {
      state.color = color;
      localStorage.setItem('live_editor_color', color);
      renderColorGrid();
    });
    elements.colorGrid.appendChild(button);
  });
}

async function submitLogin(role, credentials) {
  if (!state.color) {
    setMessage(elements.loginMessage, 'Choose a cursor color.', 'error');
    return;
  }
  setMessage(elements.loginMessage, 'Checking your details...', 'success');
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, ...credentials }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to log in.');
    state.authToken = data.token;
    state.user = data.user;
    localStorage.setItem('live_editor_auth_token', state.authToken);
    localStorage.setItem('live_editor_color', state.color);
    updateSignedInUI();
    setMessage(elements.loginMessage, 'Login successful. Joining the live editor...', 'success');
    tryJoinSocket();
  } catch (error) {
    setMessage(elements.loginMessage, error.message, 'error');
  }
}

function updateSignedInUI() {
  if (!state.user) return;
  elements.userProfileBadge.style.display = 'flex';
  elements.myAvatar.textContent = state.user.username.charAt(0).toUpperCase();
  elements.myAvatar.style.backgroundColor = safeColor(state.color);
  elements.myUsername.textContent = state.user.username;
  elements.myAdminCrown.style.display = state.user.role === 'admin' ? 'inline' : 'none';
  elements.btnSettings.style.display = 'inline-flex';
  elements.settingsButtonLabel.textContent = state.user.role === 'admin' ? 'Admin Settings' : 'Your Code Access';
  elements.btnAddFile.style.display = state.user.role === 'admin' ? 'inline-flex' : 'none';
  renderFileTabs();
}

function clearAuthentication() {
  state.authToken = '';
  state.user = null;
  state.joined = false;
  state.editableOwnerIds = new Set();
  state.globalEditor = false;
  localStorage.removeItem('live_editor_auth_token');
}

async function logout() {
  try {
    if (state.authToken) {
      await authorizedFetch('/api/auth/logout', { method: 'POST' });
    }
  } finally {
    clearAuthentication();
    localStorage.removeItem('live_editor_color');
    if (state.socket) state.socket.close();
    window.location.reload();
  }
}

function initializeWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  state.socket = new WebSocket(`${protocol}//${window.location.host}/ws/${state.clientId}`);
  setSocketStatus('Connecting...', false);

  state.socket.addEventListener('open', () => {
    state.socketReady = true;
    setSocketStatus('Connected', true);
    tryJoinSocket();
  });

  state.socket.addEventListener('message', (event) => {
    try {
      handleWsMessage(JSON.parse(event.data));
    } catch (error) {
      console.error('Invalid server message:', error);
    }
  });

  state.socket.addEventListener('close', () => {
    state.socketReady = false;
    state.joined = false;
    setSocketStatus('Reconnecting...', false);
    setTimeout(initializeWebSocket, 2000);
  });

  state.socket.addEventListener('error', () => {
    setSocketStatus('Connection error', false);
  });
}

function setSocketStatus(text, connected) {
  elements.wsStatusText.textContent = text;
  elements.wsStatus.classList.toggle('connected', connected);
  elements.chatSidebar.classList.toggle('socket-offline', !connected);
}

function tryJoinSocket() {
  if (!state.socketReady || !state.authToken || !state.user || !state.color || state.joined) return;
  sendWsMessage({
    type: 'join',
    token: state.authToken,
    color: state.color,
  });
}

function sendWsMessage(message) {
  if (state.socket?.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify(message));
  }
}

function handleWsMessage(data) {
  switch (data.type) {
    case 'init':
      applyWorkspace(data.workspace, data.line_authors);
      state.palette = data.palette || state.palette;
      state.claimedColors = data.claimed_colors || {};
      state.activeUsers = data.active_users || [];
      state.students = data.students || [];
      chooseAvailableColor();
      renderColorGrid();
      renderPresence();
      tryJoinSocket();
      break;

    case 'join_success':
      state.joined = true;
      state.user = { ...state.user, ...data.user };
      state.chatHistory = data.messages || [];
      state.students = data.students || state.students;
      updateSignedInUI();
      renderPresence();
      renderChatMessages();
      renderDmConversations();
      updateDmRecipientDropdown();
      loadAccessSettings();
      if (elements.dlgLogin.open) elements.dlgLogin.close();
      showToast(`Welcome, ${state.user.username}${state.user.role === 'admin' ? ' ♛' : ''}.`, 'success');
      break;

    case 'presence_updated':
    case 'user_joined':
    case 'user_left':
      state.activeUsers = data.active_users || [];
      state.claimedColors = data.claimed_colors || {};
      state.students = data.students || state.students;
      renderPresence();
      renderColorGrid();
      updateDmRecipientDropdown();
      renderDmConversations();
      syncChatView();
      if (isSettingsDialogOpen()) loadAccessSettings();
      break;

    case 'student_records_updated':
      state.students = data.students || [];
      if (data.active_users) state.activeUsers = data.active_users;
      updateDmRecipientDropdown();
      renderPresence();
      if (elements.dlgAdminSettings.open) {
        loadAdminStudents();
        loadAccessSettings();
      }
      if (elements.dlgStudentSettings.open) loadAccessSettings();
      break;

    case 'workspace_updated':
      applyWorkspace(data.workspace, data.line_authors);
      if (data.requester_id === state.clientId && data.created_file_id) {
        switchFile(data.created_file_id);
        if (elements.dlgNewFile.open) elements.dlgNewFile.close();
      }
      break;

    case 'code_delta':
      applyRemoteDelta(data);
      break;

    case 'file_state':
      applyAuthoritativeFile(data);
      break;

    case 'permission_denied':
      showToast(data.message || 'This code is read-only.', 'error');
      if (data.file) applyAuthoritativeFile({
        file: data.file,
        line_authors: data.line_authors,
      });
      break;

    case 'cursor_update':
      renderRemoteCursor(data);
      break;

    case 'typing_update':
      updateTypingState(data);
      break;

    case 'typing_line_update':
      updateRemoteLineHighlight(data);
      break;

    case 'chat_history':
      state.chatHistory = data.messages || [];
      renderChatMessages();
      renderDmConversations();
      break;

    case 'chat_message':
      receiveChatMessage(data.message);
      break;

    case 'account_name_updated':
      applyAccountNameUpdate(data);
      break;

    case 'access_updated':
      loadAccessSettings();
      break;

    case 'auth_error':
      showToast(data.message || 'Authentication failed.', 'error');
      clearAuthentication();
      showLoginDialog();
      break;

    case 'error':
      showToast(data.message || 'Something went wrong.', 'error');
      setMessage(elements.newFileMessage, data.message || '', 'error');
      break;

    default:
      break;
  }
}

function applyWorkspace(workspace, allLineAuthors) {
  if (!workspace) return;
  const previousActive = state.activeFileId;
  state.files = workspace.files || [];
  state.tabLimit = workspace.tab_limit || 6;
  state.lineAuthors = allLineAuthors || state.lineAuthors;
  if (!state.files.some((file) => file.id === previousActive)) {
    state.activeFileId = state.files[0]?.id || null;
  }
  renderFileTabs();
  loadActiveFileIntoEditor();
}

function getActiveFile() {
  return state.files.find((file) => file.id === state.activeFileId) || null;
}

function getActiveLineAuthors() {
  return state.lineAuthors[state.activeFileId] || {};
}

function renderFileTabs() {
  elements.fileTabs.replaceChildren();
  state.files.forEach((file) => {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = `file-tab${file.id === state.activeFileId ? ' active' : ''}`;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', file.id === state.activeFileId ? 'true' : 'false');

    const languageDot = document.createElement('span');
    languageDot.className = `file-language-dot ${file.language}`;
    languageDot.textContent = file.language === 'cpp' ? 'C++' : 'Py';
    const name = document.createElement('span');
    name.className = 'file-tab-name';
    name.textContent = file.name;
    tab.append(languageDot, name);
    tab.addEventListener('click', () => switchFile(file.id));

    if (state.user?.role === 'admin' && state.files.length > 1) {
      const close = document.createElement('span');
      close.className = 'file-tab-close';
      close.setAttribute('role', 'button');
      close.setAttribute('aria-label', `Close ${file.name}`);
      close.textContent = '×';
      close.addEventListener('click', (event) => {
        event.stopPropagation();
        if (confirm(`Close "${file.name}" for everyone?`)) {
          sendWsMessage({ type: 'delete_file', file_id: file.id });
        }
      });
      tab.appendChild(close);
    }
    elements.fileTabs.appendChild(tab);
  });
  elements.tabCountLabel.textContent = `${state.files.length} / ${state.tabLimit}`;
  elements.btnAddFile.disabled = state.files.length >= state.tabLimit;
}

function switchFile(fileId) {
  if (!state.files.some((file) => file.id === fileId)) return;
  const current = getActiveFile();
  if (current && state.editor && !state.isRemoteChange) {
    current.code = state.editor.getValue();
  }
  state.activeFileId = fileId;
  clearAllRemoteCursors();
  renderFileTabs();
  loadActiveFileIntoEditor();
  sendWsMessage({
    type: 'cursor_change',
    file_id: fileId,
    cursor: state.editor.getCursor(),
  });
}

function loadActiveFileIntoEditor() {
  const file = getActiveFile();
  if (!file || !state.editor) return;
  state.isRemoteChange = true;
  state.editor.setOption('mode', file.language === 'cpp' ? 'text/x-c++src' : 'python');
  if (state.editor.getValue() !== file.code) state.editor.setValue(file.code || '');
  state.isRemoteChange = false;
  elements.currentFileTag.replaceChildren();
  const icon = document.createElement('i');
  icon.setAttribute('data-lucide', 'file-code-2');
  elements.currentFileTag.append(icon, document.createTextNode(` ${file.name}`));
  elements.currentLanguageBadge.textContent = file.language === 'cpp' ? 'C++' : 'Python';
  elements.currentLanguageBadge.className = `language-badge ${file.language}`;
  elements.runButtonLabel.textContent = file.language === 'cpp' ? 'Compile & Run C++' : 'Run Python';
  loadProgramInput(file.id);
  lucide.createIcons();
  state.editor.refresh();
}

function programInputStorageKey(fileId) {
  return `live_editor_program_input_${fileId || 'default'}`;
}

function loadProgramInput(fileId) {
  try {
    elements.programInput.value = localStorage.getItem(programInputStorageKey(fileId)) || '';
  } catch (_error) {
    elements.programInput.value = '';
  }
}

function saveProgramInput() {
  try {
    localStorage.setItem(
      programInputStorageKey(state.activeFileId),
      elements.programInput.value,
    );
  } catch (_error) {
    showToast('Program input could not be saved in this browser.', 'error');
  }
}

function applyRemoteDelta(data) {
  const file = state.files.find((item) => item.id === data.file_id);
  if (!file || !Array.isArray(data.text)) return;
  const replacement = data.text.join('\n');
  file.code = applyTextDelta(file.code, data.from, data.to, replacement);
  file.revision = data.revision ?? file.revision;
  state.lineAuthors[data.file_id] = data.line_authors || {};
  if (state.activeFileId !== data.file_id) return;
  const scroll = state.editor.getScrollInfo();
  state.isRemoteChange = true;
  state.editor.replaceRange(replacement, data.from, data.to, 'remote');
  state.isRemoteChange = false;
  state.editor.scrollTo(scroll.left, scroll.top);
}

function applyTextDelta(code, from, to, replacement) {
  const lines = String(code || '').split('\n');
  const offsetFor = (position) => {
    const line = Math.max(0, Math.min(position.line || 0, lines.length - 1));
    const ch = Math.max(0, Math.min(position.ch || 0, lines[line].length));
    return lines.slice(0, line).reduce((total, value) => total + value.length + 1, 0) + ch;
  };
  const start = offsetFor(from);
  const end = offsetFor(to);
  return code.slice(0, start) + replacement + code.slice(end);
}

function applyAuthoritativeFile(data) {
  const index = state.files.findIndex((file) => file.id === data.file?.id);
  if (index === -1) return;
  state.files[index] = data.file;
  state.lineAuthors[data.file.id] = data.line_authors || {};
  if (state.activeFileId !== data.file.id) return;
  state.isRemoteChange = true;
  state.editor.setValue(data.file.code || '');
  state.isRemoteChange = false;
  if (data.requester_id === state.clientId && Number.isInteger(data.focus_line)) {
    const line = Math.min(data.focus_line, state.editor.lineCount() - 1);
    state.editor.setCursor({ line, ch: 0 });
    state.editor.focus();
  }
}

function safeColor(value) {
  return /^#[0-9A-Fa-f]{6}$/.test(value || '') ? value : '#38BDF8';
}

function renderRemoteCursor(data) {
  removeRemoteCursor(data.id);
  if (!data.cursor || !data.username || data.file_id !== state.activeFileId) return;
  const cursor = document.createElement('span');
  cursor.className = 'remote-cursor';
  cursor.style.borderColor = safeColor(data.color);
  cursor.classList.toggle('is-typing', state.typingUsers.has(data.id));

  const marker = state.editor.setBookmark(data.cursor, {
    widget: cursor,
    insertLeft: true,
  });
  state.remoteCursors.set(data.id, {
    marker,
    element: cursor,
    fileId: data.file_id,
  });
}

function removeRemoteCursor(id) {
  const cursor = state.remoteCursors.get(id);
  if (cursor) {
    cursor.marker.clear();
    state.remoteCursors.delete(id);
  }
}

function clearAllRemoteCursors() {
  [...state.remoteCursors.keys()].forEach(removeRemoteCursor);
}

function updateTypingState(data) {
  if (data.is_typing) state.typingUsers.add(data.id);
  else state.typingUsers.delete(data.id);
  const remote = state.remoteCursors.get(data.id);
  remote?.element.classList.toggle('is-typing', Boolean(data.is_typing));

  const typingNames = state.activeUsers
    .filter((user) => state.typingUsers.has(user.id))
    .map((user) => `${user.username}${user.role === 'admin' ? ' ♛' : ''}`);
  if (data.is_typing && !typingNames.includes(data.username)) {
    typingNames.push(`${data.username}${data.role === 'admin' ? ' ♛' : ''}`);
  }
  elements.typingBanner.style.display = typingNames.length ? 'flex' : 'none';
  elements.typingBannerText.textContent = typingNames.length
    ? `${typingNames.join(', ')} ${typingNames.length === 1 ? 'is' : 'are'} editing...`
    : '';
}

function updateRemoteLineHighlight(data) {
  if (data.file_id !== state.activeFileId) return;
  const safeId = String(data.id).replace(/[^A-Za-z0-9_-]/g, '_');
  const key = `${safeId}_${data.file_id}_${data.line}`;
  const className = `typing-line-${safeId}`;
  clearTimeout(state.lineTypingTimeouts.get(key));
  state.editor.removeLineClass(data.line, 'background', className);

  if (!data.is_typing) return;
  let style = document.getElementById(`typing-style-${safeId}`);
  if (!style) {
    style = document.createElement('style');
    style.id = `typing-style-${safeId}`;
    document.head.appendChild(style);
  }
  style.textContent = `.${className} { background-color: ${hexToRgba(safeColor(data.color), 0.20)} !important; }`;
  state.editor.addLineClass(data.line, 'background', className);
  state.lineTypingTimeouts.set(key, setTimeout(() => {
    state.editor.removeLineClass(data.line, 'background', className);
    state.lineTypingTimeouts.delete(key);
  }, 1500));
}

function hexToRgba(hex, alpha) {
  const number = parseInt(hex.slice(1), 16);
  return `rgba(${(number >> 16) & 255}, ${(number >> 8) & 255}, ${number & 255}, ${alpha})`;
}

function renderPresence() {
  elements.avatarGroup.replaceChildren();
  const active = state.activeUsers.filter((user) => user.username);
  const label = elements.presenceBar.querySelector('.presence-label');
  label.textContent = `Active (${active.length}):`;
  active.forEach((user) => {
    const pill = document.createElement('div');
    pill.className = 'user-pill';
    pill.style.backgroundColor = safeColor(user.color);
    const name = document.createElement('span');
    name.textContent = `${user.username}${user.role === 'admin' ? ' ♛' : ''}`;
    pill.appendChild(name);
    if (user.is_typing) {
      const typing = document.createElement('span');
      typing.className = 'typing-indicator';
      pill.appendChild(typing);
    }
    elements.avatarGroup.appendChild(pill);
  });
}

async function authorizedFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.authToken) headers.set('Authorization', `Bearer ${state.authToken}`);
  return fetch(url, { ...options, headers });
}

async function loadAccessSettings() {
  if (!state.authToken || !state.user) return;
  try {
    const response = await authorizedFetch('/api/access');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to load access settings.');

    if (data.mode === 'global') {
      state.globalEditor = false;
      state.editableOwnerIds = new Set();
      renderAccessList(elements.adminGlobalAccessList, data.users, 'global');
    } else {
      state.globalEditor = Boolean(data.global_editor);
      state.editableOwnerIds = new Set(data.editable_owner_ids || []);
      renderAccessList(elements.studentCodeAccessList, data.users, 'owner');
    }
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function renderAccessList(container, users, mode) {
  container.replaceChildren();
  if (!users?.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'No other students are available.';
    container.appendChild(empty);
    return;
  }
  users.forEach((user) => {
    const row = document.createElement('div');
    row.className = 'access-row';
    const identity = document.createElement('div');
    identity.className = 'access-identity';
    const avatar = document.createElement('span');
    avatar.className = 'access-avatar';
    avatar.textContent = user.full_name.charAt(0).toUpperCase();
    const details = document.createElement('span');
    const name = document.createElement('strong');
    name.textContent = user.full_name;
    const status = document.createElement('small');
    status.textContent = user.online ? 'Online' : 'Offline';
    status.className = user.online ? 'online-text' : 'offline-text';
    details.append(name, status);
    identity.append(avatar, details);

    const switchLabel = document.createElement('label');
    switchLabel.className = 'access-switch';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = Boolean(user.enabled);
    checkbox.setAttribute('aria-label', `Allow ${user.full_name}`);
    const track = document.createElement('span');
    track.className = 'access-switch-track';
    const switchText = document.createElement('span');
    switchText.className = 'access-switch-text';
    switchText.textContent = checkbox.checked ? 'On' : 'Off';
    checkbox.addEventListener('change', async () => {
      switchText.textContent = checkbox.checked ? 'On' : 'Off';
      const endpoint = mode === 'global'
        ? `/api/access/global/${encodeURIComponent(user.account_id)}`
        : `/api/access/owner/${encodeURIComponent(user.account_id)}`;
      const response = await authorizedFetch(endpoint, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: checkbox.checked }),
      });
      if (!response.ok) {
        const data = await response.json();
        checkbox.checked = !checkbox.checked;
        switchText.textContent = checkbox.checked ? 'On' : 'Off';
        showToast(data.detail || 'Unable to update access.', 'error');
      }
    });
    switchLabel.append(checkbox, track, switchText);
    row.append(identity, switchLabel);
    container.appendChild(row);
  });
}

async function openSettings() {
  if (state.user?.role === 'admin') {
    elements.txtAdminDisplayName.value = state.user.username;
    elements.numTabLimit.value = state.tabLimit;
    await Promise.all([loadAdminStudents(), loadAccessSettings()]);
    elements.dlgAdminSettings.showModal();
  } else {
    await loadAccessSettings();
    elements.dlgStudentSettings.showModal();
  }
  lucide.createIcons();
}

function isSettingsDialogOpen() {
  return elements.dlgAdminSettings.open || elements.dlgStudentSettings.open;
}

async function loadAdminStudents() {
  try {
    const response = await authorizedFetch('/api/students');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to load student records.');
    renderStudentRecords(data.students || []);
  } catch (error) {
    setMessage(elements.studentRecordMessage, error.message, 'error');
  }
}

function renderStudentRecords(students) {
  elements.studentRecordsList.replaceChildren();
  students.forEach((student) => {
    const row = document.createElement('div');
    row.className = 'student-record-row';
    const details = document.createElement('div');
    const heading = document.createElement('strong');
    heading.textContent = student.full_name;
    const metadata = document.createElement('small');
    metadata.textContent = `${student.student_id} • DOB ${formatDisplayDate(student.date_of_birth)}`;
    details.append(heading, metadata);
    if (student.other_info && Object.keys(student.other_info).length) {
      const extra = document.createElement('small');
      extra.textContent = Object.values(student.other_info).join(' • ');
      details.appendChild(extra);
    }

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn btn-danger btn-sm';
    remove.textContent = 'Remove';
    remove.addEventListener('click', async () => {
      if (!confirm(`Remove ${student.full_name}? Their active session will be closed.`)) return;
      const response = await authorizedFetch(`/api/students/${encodeURIComponent(student.account_id)}`, {
        method: 'DELETE',
      });
      const data = await response.json();
      if (!response.ok) {
        showToast(data.detail || 'Unable to remove student.', 'error');
        return;
      }
      showToast(`${student.full_name} was removed.`, 'success');
      await Promise.all([loadAdminStudents(), loadAccessSettings()]);
    });
    row.append(details, remove);
    elements.studentRecordsList.appendChild(row);
  });
}

function formatDisplayDate(value) {
  const [year, month, day] = String(value || '').split('-');
  return year && month && day ? `${day}/${month}/${year}` : value;
}

function applyAccountNameUpdate(data) {
  state.activeUsers = data.active_users || state.activeUsers;
  if (state.user?.account_id === data.account_id) {
    state.user.username = data.username;
    updateSignedInUI();
  }
  Object.values(state.lineAuthors).forEach((authors) => {
    Object.values(authors).forEach((info) => {
      if (info.account_id === data.account_id) info.author = data.username;
    });
  });
  renderPresence();
}

async function runCurrentFile() {
  const file = getActiveFile();
  if (!file || !state.joined) {
    showToast('Log in before running code.', 'error');
    return;
  }
  elements.consoleOutput.className = 'console-output';
  elements.consoleOutput.textContent = file.language === 'cpp'
    ? 'Compiling and running C++...'
    : 'Running Python...';
  elements.outputDrawer.classList.remove('minimized');
  elements.execTimeTag.style.display = 'none';
  sendWsMessage({ type: 'code_run_notice', file_id: file.id });

  try {
    const response = await authorizedFetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: state.editor.getValue(),
        language: file.language,
        stdin: elements.programInput.value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Execution failed.');
    elements.execTimeTag.textContent = `${data.elapsed}s`;
    elements.execTimeTag.style.display = 'inline-block';
    if (data.stderr) {
      elements.consoleOutput.className = 'console-output stderr';
      const stage = data.stage === 'compile' ? 'Compiler output:\n' : '';
      elements.consoleOutput.textContent = `${stage}${data.stderr}${data.stdout ? `\n${data.stdout}` : ''}`;
    } else {
      elements.consoleOutput.textContent = data.stdout || '(Completed successfully with no output)';
    }
  } catch (error) {
    elements.consoleOutput.className = 'console-output stderr';
    elements.consoleOutput.textContent = error.message;
  }
}

async function saveSnapshot() {
  const file = getActiveFile();
  if (!file) return;
  const label = prompt('Snapshot label:', `${file.name} ${new Date().toLocaleTimeString()}`);
  if (!label) return;
  const response = await authorizedFetch('/api/snapshots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      label,
      code: state.editor.getValue(),
      file_id: file.id,
      file_name: file.name,
      language: file.language,
    }),
  });
  const data = await response.json();
  showToast(response.ok ? 'Snapshot saved.' : (data.detail || 'Unable to save snapshot.'), response.ok ? 'success' : 'error');
}

async function loadSnapshots() {
  const response = await authorizedFetch('/api/snapshots');
  const data = await response.json();
  elements.snapshotsList.replaceChildren();
  if (!response.ok) {
    const error = document.createElement('p');
    error.className = 'empty-state';
    error.textContent = data.detail || 'Unable to load snapshots.';
    elements.snapshotsList.appendChild(error);
    return;
  }
  if (!data.snapshots?.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'No saved snapshots yet.';
    elements.snapshotsList.appendChild(empty);
    return;
  }
  data.snapshots.forEach((snapshot) => {
    const card = document.createElement('div');
    card.className = 'snapshot-card';
    const info = document.createElement('div');
    info.className = 'snapshot-info';
    const title = document.createElement('h4');
    title.textContent = snapshot.label;
    const metadata = document.createElement('div');
    metadata.className = 'snapshot-meta';
    metadata.textContent = `${snapshot.file_name || 'Legacy file'} • ${snapshot.language === 'cpp' ? 'C++' : 'Python'} • ${snapshot.author} • ${snapshot.timestamp}`;
    info.append(title, metadata);
    const restore = document.createElement('button');
    restore.type = 'button';
    restore.className = 'btn btn-secondary btn-sm';
    restore.textContent = 'Restore';
    restore.addEventListener('click', () => {
      const target = state.files.find((file) => file.id === snapshot.file_id) || getActiveFile();
      if (!target || !confirm(`Restore this snapshot into "${target.name}"?`)) return;
      switchFile(target.id);
      state.editor.setValue(snapshot.code || '');
      elements.dlgSnapshots.close();
    });
    card.append(info, restore);
    elements.snapshotsList.appendChild(card);
  });
}

function participantDirectory() {
  const directory = new Map();
  state.students.forEach((student) => {
    directory.set(student.account_id, {
      account_id: student.account_id,
      username: student.full_name,
      role: 'student',
      online: Boolean(student.online),
      color: '#64748B',
    });
  });
  state.activeUsers.forEach((user) => {
    directory.set(user.account_id, {
      account_id: user.account_id,
      username: user.username,
      role: user.role,
      online: true,
      color: safeColor(user.color),
    });
  });
  return directory;
}

function updateDmRecipientDropdown() {
  const selected = elements.selDmRecipient.value;
  const startedConversations = startedDmAccountIds();
  elements.selDmRecipient.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.disabled = true;
  placeholder.selected = true;
  placeholder.textContent = 'Select a user to message...';
  elements.selDmRecipient.appendChild(placeholder);
  const availablePeople = [...participantDirectory().values()]
    .filter((person) => (
      person.account_id
      && person.account_id !== state.user?.account_id
      && !startedConversations.has(person.account_id)
    ))
    .sort((a, b) => a.username.localeCompare(b.username));
  availablePeople.forEach((person) => {
    const option = document.createElement('option');
    option.value = person.account_id;
    option.textContent = `${person.username}${person.role === 'admin' ? ' ♛' : ''} (${person.online ? 'Online' : 'Offline'})`;
    elements.selDmRecipient.appendChild(option);
  });
  if (!availablePeople.length) {
    placeholder.textContent = 'No new users available';
  }
  if ([...elements.selDmRecipient.options].some((option) => option.value === selected)) {
    elements.selDmRecipient.value = selected;
  }
}

function startedDmAccountIds() {
  const accountIds = new Set();
  if (!state.user) return accountIds;
  state.chatHistory.forEach((message) => {
    if (message.target === 'group' || !message.sender_account_id || !message.target_account_id) return;
    if (message.sender_account_id === state.user.account_id) {
      accountIds.add(message.target_account_id);
    } else if (message.target_account_id === state.user.account_id) {
      accountIds.add(message.sender_account_id);
    }
  });
  accountIds.delete(state.user.account_id);
  return accountIds;
}

function receiveChatMessage(message) {
  if (!message) return;
  state.chatHistory.push(message);
  renderChatMessages();
  renderDmConversations();
  const fromOther = message.sender_account_id !== state.user?.account_id;
  const isDirect = message.target !== 'group';
  if (fromOther && isDirect) {
    showDmNotification(message);
    if (
      isChatCollapsed
      || state.currentChatTab !== 'private'
      || state.activeDmAccountId !== message.sender_account_id
    ) {
      state.unreadCount += 1;
      updateUnreadBadge();
    } else {
      markDmRead(message.sender_account_id);
    }
  } else if (fromOther && isChatCollapsed) {
    state.unreadCount += 1;
    updateUnreadBadge();
  }
}

function renderChatMessages() {
  elements.chatMessagesContainer.replaceChildren();
  const filtered = state.chatHistory.filter((message) => {
    if (state.currentChatTab === 'group') return message.target === 'group';
    if (!state.activeDmAccountId || message.target === 'group') return false;
    return (
      message.sender_account_id === state.user?.account_id
      && message.target_account_id === state.activeDmAccountId
    ) || (
      message.target_account_id === state.user?.account_id
      && message.sender_account_id === state.activeDmAccountId
    );
  });

  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'chat-empty-state';
    const title = document.createElement('p');
    title.textContent = state.currentChatTab === 'group'
      ? 'Classroom Group Channel'
      : state.activeDmAccountId
        ? 'No messages in this conversation'
        : 'Select a direct-message conversation';
    const hint = document.createElement('span');
    hint.textContent = state.currentChatTab === 'group' ? 'No group messages yet.' : 'Messages are private to both users.';
    empty.append(title, hint);
    elements.chatMessagesContainer.appendChild(empty);
    return;
  }

  filtered.forEach((message) => {
    const own = message.sender_account_id === state.user?.account_id
      || (!message.sender_account_id && message.sender === state.user?.username);
    const card = document.createElement('div');
    card.className = `chat-msg-card ${own ? 'own' : 'other'}${message.target !== 'group' ? ' private' : ''}`;
    const header = document.createElement('div');
    header.className = 'chat-msg-header';
    const sender = document.createElement('span');
    sender.className = 'chat-sender-name';
    sender.style.color = safeColor(message.color);
    sender.textContent = own
      ? 'You'
      : `${message.sender || 'User'}${message.sender_role === 'admin' ? ' ♛' : ''}`;
    const timestamp = document.createElement('span');
    timestamp.className = 'chat-timestamp';
    timestamp.textContent = message.timestamp || '';
    header.append(sender, timestamp);
    const bubble = document.createElement('div');
    bubble.className = 'chat-msg-bubble';
    bubble.textContent = message.text || '';
    card.append(header, bubble);
    elements.chatMessagesContainer.appendChild(card);
  });
  elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;
}

function renderDmConversations() {
  elements.dmConversationsList.replaceChildren();
  if (!state.user) return;
  const directory = participantDirectory();
  const conversations = new Map();
  state.chatHistory.forEach((message) => {
    if (message.target === 'group' || !message.sender_account_id || !message.target_account_id) return;
    const otherId = message.sender_account_id === state.user.account_id
      ? message.target_account_id
      : message.sender_account_id;
    if (otherId === state.user.account_id) return;
    const entry = conversations.get(otherId) || {
      accountId: otherId,
      lastMessage: '',
      lastId: 0,
      unread: 0,
    };
    if ((message.id || 0) >= entry.lastId) {
      entry.lastMessage = message.text;
      entry.lastId = message.id || 0;
      entry.timestamp = message.timestamp || '';
    }
    if (
      message.sender_account_id === otherId
      && !(message.read_by || []).includes(state.user.account_id)
    ) entry.unread += 1;
    conversations.set(otherId, entry);
  });

  const sorted = [...conversations.values()].sort((a, b) => b.lastId - a.lastId);
  if (!sorted.length) {
    const empty = document.createElement('div');
    empty.className = 'dm-empty-list';
    empty.textContent = 'No chats started yet. Select a user above to begin.';
    elements.dmConversationsList.appendChild(empty);
    return;
  }

  sorted.forEach((conversation) => {
    const person = directory.get(conversation.accountId) || {
      username: 'Former student',
      role: 'student',
      online: false,
      color: '#64748B',
    };
    const row = document.createElement('button');
    row.type = 'button';
    row.className = `dm-item${state.activeDmAccountId === conversation.accountId ? ' selected' : ''}`;
    const avatarBox = document.createElement('span');
    avatarBox.className = 'dm-avatar-box';
    const avatar = document.createElement('span');
    avatar.className = 'dm-avatar';
    avatar.style.backgroundColor = safeColor(person.color);
    avatar.textContent = person.username.charAt(0).toUpperCase();
    const status = document.createElement('span');
    status.className = `status-dot-badge ${person.online ? 'online' : 'offline'}`;
    avatarBox.append(avatar, status);
    const details = document.createElement('span');
    details.className = 'dm-details';
    const name = document.createElement('strong');
    name.className = 'dm-username';
    name.textContent = `${person.username}${person.role === 'admin' ? ' ♛' : ''}`;
    const preview = document.createElement('small');
    preview.className = 'dm-last-msg';
    preview.textContent = messagePreview(conversation.lastMessage);
    details.append(name, preview);
    row.append(avatarBox, details);
    if (conversation.unread) {
      const unread = document.createElement('span');
      unread.className = 'dm-unread-pill';
      unread.textContent = String(conversation.unread);
      row.appendChild(unread);
    }
    row.addEventListener('click', () => openDm(conversation.accountId));
    elements.dmConversationsList.appendChild(row);
  });
}

function messagePreview(text) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  return words.length <= 5 ? words.join(' ') : `${words.slice(0, 5).join(' ')}...`;
}

function openDm(accountId) {
  if (!accountId) return;
  state.activeDmAccountId = accountId;
  state.currentChatTab = 'private';
  elements.tabPrivateChat.classList.add('active');
  elements.tabGroupChat.classList.remove('active');
  elements.selDmRecipient.value = accountId;
  elements.dmSelectorBox.style.display = 'none';
  syncChatView();
  markDmRead(accountId);
  renderDmConversations();
  renderChatMessages();
  setTimeout(() => elements.txtChatMessage.focus(), 0);
}

function showDmList() {
  state.activeDmAccountId = null;
  elements.dmSelectorBox.style.display = 'none';
  elements.selDmRecipient.value = '';
  syncChatView();
  updateDmRecipientDropdown();
  renderDmConversations();
  renderChatMessages();
}

function syncChatView() {
  const directMessages = state.currentChatTab === 'private';
  const conversationOpen = directMessages && Boolean(state.activeDmAccountId);
  elements.chatSidebar.classList.toggle('dm-list-view', directMessages && !conversationOpen);
  elements.dmSubSidebar.style.display = directMessages && !conversationOpen ? 'flex' : 'none';
  elements.dmConversationHeader.style.display = conversationOpen ? 'flex' : 'none';
  elements.chatMessagesContainer.style.display = !directMessages || conversationOpen ? 'flex' : 'none';
  elements.frmChat.style.display = !directMessages || conversationOpen ? 'flex' : 'none';

  if (!conversationOpen) {
    elements.txtChatMessage.placeholder = 'Type a message...';
    return;
  }

  const person = participantDirectory().get(state.activeDmAccountId) || {
    username: 'Former student',
    role: 'student',
    online: false,
    color: '#64748B',
  };
  elements.dmActiveAvatar.style.backgroundColor = safeColor(person.color);
  elements.dmActiveAvatar.textContent = person.username.charAt(0).toUpperCase();
  elements.dmActiveName.textContent = `${person.username}${person.role === 'admin' ? ' ♛' : ''}`;
  elements.dmActiveStatus.textContent = person.online ? 'Online' : 'Offline';
  elements.dmActiveStatus.className = person.online ? 'online-text' : 'offline-text';
  elements.txtChatMessage.placeholder = `Message ${person.username}...`;
}

function markDmRead(accountId) {
  sendWsMessage({ type: 'mark_read', target_account_id: accountId });
}

function showDmNotification(message) {
  const toast = document.createElement('button');
  toast.type = 'button';
  toast.className = 'toast-card';
  const avatar = document.createElement('span');
  avatar.className = 'toast-avatar';
  avatar.style.backgroundColor = safeColor(message.color);
  avatar.textContent = (message.sender || 'U').charAt(0).toUpperCase();
  const bodyElement = document.createElement('span');
  bodyElement.className = 'toast-body';
  const header = document.createElement('span');
  header.className = 'toast-header';
  const sender = document.createElement('strong');
  sender.className = 'toast-sender';
  sender.textContent = `${message.sender}${message.sender_role === 'admin' ? ' ♛' : ''}`;
  const tag = document.createElement('span');
  tag.className = 'toast-tag';
  tag.textContent = '🔒 DM';
  const preview = document.createElement('span');
  preview.className = 'toast-text';
  preview.textContent = messagePreview(message.text);
  header.append(sender, tag);
  bodyElement.append(header, preview);
  toast.append(avatar, bodyElement);
  toast.addEventListener('click', () => {
    expandChat();
    openDm(message.sender_account_id);
    toast.remove();
  });
  elements.toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 6000);
}

function updateUnreadBadge() {
  if (state.unreadCount > 0 && isChatCollapsed) {
    elements.chatUnreadBadge.textContent = state.unreadCount > 9 ? '9+' : String(state.unreadCount);
    elements.chatUnreadBadge.style.display = 'inline-block';
  } else {
    elements.chatUnreadBadge.style.display = 'none';
  }
}

function restoreChatLayout() {
  elements.chatSidebar.classList.toggle('collapsed', isChatCollapsed);
  elements.chatSidebar.classList.toggle('minimized-chat', isChatMinimized);
  const savedWidth = parseInt(localStorage.getItem('chat_sidebar_width') || '420', 10);
  if (window.innerWidth >= 768 && savedWidth >= 320 && savedWidth <= 700) {
    elements.chatSidebar.style.width = `${savedWidth}px`;
  }
}

function expandChat() {
  isChatCollapsed = false;
  isChatMinimized = false;
  localStorage.setItem('chat_collapsed', 'false');
  localStorage.setItem('chat_minimized', 'false');
  elements.chatSidebar.classList.remove('collapsed', 'minimized-chat');
  state.unreadCount = 0;
  updateUnreadBadge();
}

function bindInterfaceEvents() {
  elements.btnThemeToggle.addEventListener('click', () => {
    setTheme(body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });
  elements.btnFontInc.addEventListener('click', () => setFontSize(currentFontSize + 1));
  elements.btnFontDec.addEventListener('click', () => setFontSize(currentFontSize - 1));

  elements.btnChooseAdmin.addEventListener('click', () => selectLoginRole('admin'));
  elements.btnChooseStudent.addEventListener('click', () => selectLoginRole('student'));
  elements.btnBackFromAdmin.addEventListener('click', resetLoginChoice);
  elements.btnBackFromStudent.addEventListener('click', resetLoginChoice);
  document.querySelectorAll('.password-toggle').forEach((button) => {
    button.addEventListener('click', () => {
      const input = $(button.dataset.passwordTarget);
      input.type = input.type === 'password' ? 'text' : 'password';
      const icon = button.querySelector('i');
      icon.setAttribute('data-lucide', input.type === 'password' ? 'eye' : 'eye-off');
      lucide.createIcons();
    });
  });

  elements.frmAdminLogin.addEventListener('submit', (event) => {
    event.preventDefault();
    const password = elements.txtAdminPassword.value;
    if (!password) {
      setMessage(elements.loginMessage, 'Enter the Admin password.', 'error');
      return;
    }
    submitLogin('admin', { password });
  });

  elements.frmStudentLogin.addEventListener('submit', (event) => {
    event.preventDefault();
    const studentId = elements.txtStudentIdLogin.value.trim();
    const dateOfBirth = elements.txtStudentDobLogin.value;
    const password = elements.txtStudentPassword.value;
    if (!studentId || !dateOfBirth || !password) {
      setMessage(elements.loginMessage, 'Complete every student login field.', 'error');
      return;
    }
    submitLogin('student', {
      student_id: studentId,
      date_of_birth: dateOfBirth,
      password,
    });
  });
  elements.btnLogout.addEventListener('click', logout);

  elements.btnAddFile.addEventListener('click', () => {
    elements.frmNewFile.reset();
    setMessage(elements.newFileMessage, '');
    elements.dlgNewFile.showModal();
    elements.txtNewFileName.focus();
  });
  elements.btnCloseNewFile.addEventListener('click', () => elements.dlgNewFile.close());
  elements.frmNewFile.addEventListener('submit', (event) => {
    event.preventDefault();
    const name = elements.txtNewFileName.value.trim();
    if (!name) {
      setMessage(elements.newFileMessage, 'Enter a file name.', 'error');
      return;
    }
    sendWsMessage({
      type: 'create_file',
      name,
      language: elements.selNewFileLanguage.value,
    });
    setMessage(elements.newFileMessage, 'Creating file...', 'success');
  });

  elements.btnSettings.addEventListener('click', openSettings);
  elements.btnCloseAdminSettings.addEventListener('click', () => elements.dlgAdminSettings.close());
  elements.btnCloseStudentSettings.addEventListener('click', () => elements.dlgStudentSettings.close());
  elements.btnSaveAdminName.addEventListener('click', async () => {
    const displayName = elements.txtAdminDisplayName.value.trim();
    if (!displayName) {
      setMessage(elements.adminNameMessage, 'Enter a display name.', 'error');
      return;
    }
    const response = await authorizedFetch('/api/admin/name', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: displayName }),
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(elements.adminNameMessage, data.detail || 'Unable to change name.', 'error');
      return;
    }
    state.user.username = data.username;
    updateSignedInUI();
    setMessage(elements.adminNameMessage, 'Admin name updated.', 'success');
  });

  elements.frmAddStudent.addEventListener('submit', async (event) => {
    event.preventDefault();
    const fullName = elements.txtNewStudentName.value.trim();
    const studentId = elements.txtNewStudentId.value.trim();
    const dateOfBirth = elements.txtNewStudentDob.value;
    if (!fullName || !studentId || !dateOfBirth) {
      setMessage(elements.studentRecordMessage, 'Name, Student ID, and DOB are required.', 'error');
      return;
    }
    const otherText = elements.txtNewStudentInfo.value.trim();
    const response = await authorizedFetch('/api/students', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: fullName,
        student_id: studentId,
        date_of_birth: dateOfBirth,
        other_info: otherText ? { notes: otherText } : {},
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(elements.studentRecordMessage, data.detail || 'Unable to add student.', 'error');
      return;
    }
    elements.frmAddStudent.reset();
    setMessage(elements.studentRecordMessage, `${data.student.full_name} was added.`, 'success');
    await Promise.all([loadAdminStudents(), loadAccessSettings()]);
  });

  elements.btnSaveTabLimit.addEventListener('click', async () => {
    const tabLimit = Number(elements.numTabLimit.value);
    const response = await authorizedFetch('/api/settings/tab-limit', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tab_limit: tabLimit }),
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(elements.tabLimitMessage, data.detail || 'Unable to update tab limit.', 'error');
      return;
    }
    state.tabLimit = data.tab_limit;
    renderFileTabs();
    setMessage(elements.tabLimitMessage, `Tab limit set to ${data.tab_limit}.`, 'success');
  });

  elements.btnRunCode.addEventListener('click', runCurrentFile);
  elements.programInput.addEventListener('input', saveProgramInput);
  elements.btnClearProgramInput.addEventListener('click', () => {
    elements.programInput.value = '';
    saveProgramInput();
    elements.programInput.focus();
  });
  elements.btnCopyCode.addEventListener('click', async () => {
    await navigator.clipboard.writeText(state.editor.getValue());
    showToast('Code copied.', 'success');
  });
  elements.btnSaveSnapshot.addEventListener('click', saveSnapshot);
  elements.btnSnapshots.addEventListener('click', async () => {
    await loadSnapshots();
    elements.dlgSnapshots.showModal();
  });
  elements.btnCloseSnapshots.addEventListener('click', () => elements.dlgSnapshots.close());
  elements.btnClearOutput.addEventListener('click', () => {
    elements.consoleOutput.textContent = '';
    elements.execTimeTag.style.display = 'none';
  });
  elements.btnToggleOutput.addEventListener('click', () => {
    elements.outputDrawer.classList.toggle('minimized');
    const minimized = elements.outputDrawer.classList.contains('minimized');
    elements.iconDrawerChevron.setAttribute('data-lucide', minimized ? 'chevron-up' : 'chevron-down');
    lucide.createIcons();
  });

  elements.btnShowQr.addEventListener('click', () => elements.dlgQr.showModal());
  elements.lanBadge.addEventListener('click', () => elements.dlgQr.showModal());
  elements.btnCloseQr.addEventListener('click', () => elements.dlgQr.close());
  elements.btnCopyLanUrl.addEventListener('click', async () => {
    await navigator.clipboard.writeText(elements.txtLanUrl.value);
    showToast('Network address copied.', 'success');
  });

  elements.btnToggleChatBar.addEventListener('click', () => {
    if (isChatCollapsed) expandChat();
    else {
      isChatCollapsed = true;
      localStorage.setItem('chat_collapsed', 'true');
      elements.chatSidebar.classList.add('collapsed');
    }
  });
  elements.btnCollapseChat.addEventListener('click', () => {
    isChatCollapsed = true;
    localStorage.setItem('chat_collapsed', 'true');
    elements.chatSidebar.classList.add('collapsed');
  });
  elements.btnMinimizeChat.addEventListener('click', () => {
    isChatMinimized = !isChatMinimized;
    localStorage.setItem('chat_minimized', String(isChatMinimized));
    elements.chatSidebar.classList.toggle('minimized-chat', isChatMinimized);
  });
  elements.tabGroupChat.addEventListener('click', () => {
    state.currentChatTab = 'group';
    state.activeDmAccountId = null;
    elements.tabGroupChat.classList.add('active');
    elements.tabPrivateChat.classList.remove('active');
    syncChatView();
    renderChatMessages();
  });
  elements.tabPrivateChat.addEventListener('click', () => {
    state.currentChatTab = 'private';
    state.activeDmAccountId = null;
    elements.tabPrivateChat.classList.add('active');
    elements.tabGroupChat.classList.remove('active');
    syncChatView();
    updateDmRecipientDropdown();
    renderDmConversations();
    renderChatMessages();
  });
  elements.btnBackToDmList.addEventListener('click', showDmList);
  elements.btnNewDm.addEventListener('click', () => {
    const visible = elements.dmSelectorBox.style.display !== 'none';
    elements.dmSelectorBox.style.display = visible ? 'none' : 'block';
    if (!visible) updateDmRecipientDropdown();
  });
  elements.selDmRecipient.addEventListener('change', () => {
    elements.dmSelectorBox.style.display = 'none';
    openDm(elements.selDmRecipient.value);
  });
  elements.frmChat.addEventListener('submit', (event) => {
    event.preventDefault();
    const text = elements.txtChatMessage.value.trim();
    if (!text || !state.joined) return;
    if (state.currentChatTab === 'private' && !state.activeDmAccountId) {
      showToast('Select a user for the direct message.', 'error');
      return;
    }
    sendWsMessage({
      type: 'chat_message',
      target: state.currentChatTab === 'group' ? 'group' : 'private',
      target_account_id: state.currentChatTab === 'private' ? state.activeDmAccountId : null,
      text,
    });
    elements.txtChatMessage.value = '';
    elements.txtChatMessage.style.height = 'auto';
  });
  elements.txtChatMessage.addEventListener('input', () => {
    elements.txtChatMessage.style.height = 'auto';
    elements.txtChatMessage.style.height = `${Math.min(elements.txtChatMessage.scrollHeight, 120)}px`;
  });
  elements.txtChatMessage.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      elements.frmChat.requestSubmit();
    }
  });
  elements.btnAttachFile.addEventListener('click', () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.addEventListener('change', () => {
      const file = fileInput.files?.[0];
      if (file) elements.txtChatMessage.value += ` [Attachment: ${file.name}]`;
    });
    fileInput.click();
  });

  initializeChatResize();
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !isChatCollapsed && !document.querySelector('dialog[open]')) {
      isChatCollapsed = true;
      localStorage.setItem('chat_collapsed', 'true');
      elements.chatSidebar.classList.add('collapsed');
    }
  });
}

function initializeChatResize() {
  if (!elements.chatResizeHandle) return;
  elements.chatResizeHandle.addEventListener('pointerdown', (event) => {
    if (window.innerWidth < 768) return;
    event.preventDefault();
    elements.chatResizeHandle.setPointerCapture(event.pointerId);
    body.classList.add('is-resizing');
    elements.chatSidebar.classList.add('is-resizing');
    const move = (moveEvent) => {
      const width = Math.min(Math.max(window.innerWidth - moveEvent.clientX, 320), 700);
      elements.chatSidebar.style.width = `${width}px`;
      localStorage.setItem('chat_sidebar_width', String(width));
    };
    const end = () => {
      body.classList.remove('is-resizing');
      elements.chatSidebar.classList.remove('is-resizing');
      elements.chatResizeHandle.removeEventListener('pointermove', move);
      elements.chatResizeHandle.removeEventListener('pointerup', end);
      elements.chatResizeHandle.removeEventListener('pointercancel', end);
    };
    elements.chatResizeHandle.addEventListener('pointermove', move);
    elements.chatResizeHandle.addEventListener('pointerup', end);
    elements.chatResizeHandle.addEventListener('pointercancel', end);
  });
}

function setMessage(element, message, type = '') {
  element.textContent = message;
  element.className = `form-message${type ? ` ${type}` : ''}`;
}

function showToast(message, type = '') {
  const toast = document.createElement('div');
  toast.className = `toast-card system-toast${type ? ` ${type}` : ''}`;
  const text = document.createElement('span');
  text.className = 'toast-text';
  text.textContent = message;
  toast.appendChild(text);
  elements.toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
