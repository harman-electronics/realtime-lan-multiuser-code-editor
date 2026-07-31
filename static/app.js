// Global State
let currentUser = null;
let currentColor = null;
let currentFontSize = 15;
let socket = null;
let clientId = 'client_' + Math.random().toString(36).substring(2, 11);
let editor = null;
let isRemoteChange = false;
let typingTimeout = null;
let remoteCursors = {}; // connection_id -> marker/widget
let palette = [];
let claimedColors = {};

// DOM Elements
const body = document.body;
const btnThemeToggle = document.getElementById('btnThemeToggle');
const iconMoon = document.getElementById('iconMoon');
const iconSun = document.getElementById('iconSun');

const btnFontInc = document.getElementById('btnFontInc');
const btnFontDec = document.getElementById('btnFontDec');
const lblFontSize = document.getElementById('lblFontSize');

const lanBadge = document.getElementById('lanBadge');
const lanIpText = document.getElementById('lanIpText');
const btnShowQr = document.getElementById('btnShowQr');
const dlgQr = document.getElementById('dlgQr');
const imgQrCode = document.getElementById('imgQrCode');
const txtLanUrl = document.getElementById('txtLanUrl');
const btnCopyLanUrl = document.getElementById('btnCopyLanUrl');
const btnCloseQr = document.getElementById('btnCloseQr');

const dlgLogin = document.getElementById('dlgLogin');
const frmLogin = document.getElementById('frmLogin');
const selUsername = document.getElementById('selUsername');
const colorGrid = document.getElementById('colorGrid');
const btnSubmitLogin = document.getElementById('btnSubmitLogin');

const userProfileBadge = document.getElementById('userProfileBadge');
const myAvatar = document.getElementById('myAvatar');
const myUsername = document.getElementById('myUsername');
const btnSwitchUser = document.getElementById('btnSwitchUser');

const presenceBar = document.getElementById('presenceBar');
const avatarGroup = document.getElementById('avatarGroup');

const typingBanner = document.getElementById('typingBanner');
const typingBannerText = document.getElementById('typingBannerText');

const wsStatus = document.getElementById('wsStatus');
const wsStatusText = document.getElementById('wsStatusText');

const btnRunCode = document.getElementById('btnRunCode');
const btnCopyCode = document.getElementById('btnCopyCode');
const btnSaveSnapshot = document.getElementById('btnSaveSnapshot');

const outputDrawer = document.getElementById('outputDrawer');
const consoleOutput = document.getElementById('consoleOutput');
const execTimeTag = document.getElementById('execTimeTag');
const btnClearOutput = document.getElementById('btnClearOutput');
const btnToggleOutput = document.getElementById('btnToggleOutput');
const iconDrawerChevron = document.getElementById('iconDrawerChevron');

const btnAdmin = document.getElementById('btnAdmin');
const dlgAdmin = document.getElementById('dlgAdmin');
const btnCloseAdmin = document.getElementById('btnCloseAdmin');
const adminAuthSec = document.getElementById('adminAuthSec');
const adminContentSec = document.getElementById('adminContentSec');
const txtAdminPin = document.getElementById('txtAdminPin');
const btnVerifyPin = document.getElementById('btnVerifyPin');
const txtAllowedUsers = document.getElementById('txtAllowedUsers');
const btnSaveAdminUsers = document.getElementById('btnSaveAdminUsers');
const lstActiveAdmin = document.getElementById('lstActiveAdmin');

const btnSnapshots = document.getElementById('btnSnapshots');
const dlgSnapshots = document.getElementById('dlgSnapshots');
const btnCloseSnapshots = document.getElementById('btnCloseSnapshots');
const snapshotsList = document.getElementById('snapshotsList');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  initTheme();
  initCodeMirror();
  fetchAppInfo();
  initWebSocket();
  bindEvents();
});

// Theme Management
function initTheme() {
  const savedTheme = localStorage.getItem('editor_theme') || 'dark';
  setTheme(savedTheme);
}

function setTheme(theme) {
  body.setAttribute('data-theme', theme);
  localStorage.setItem('editor_theme', theme);
  if (theme === 'dark') {
    iconMoon.style.display = 'block';
    iconSun.style.display = 'none';
    if (editor) editor.setOption('theme', 'dracula');
  } else {
    iconMoon.style.display = 'none';
    iconSun.style.display = 'block';
    if (editor) editor.setOption('theme', 'eclipse');
  }
}

btnThemeToggle.addEventListener('click', () => {
  const current = body.getAttribute('data-theme');
  setTheme(current === 'dark' ? 'light' : 'dark');
});

// Font Size Management
function setFontSize(size) {
  currentFontSize = Math.min(Math.max(size, 12), 28);
  lblFontSize.textContent = `${currentFontSize}px`;
  const cmEl = document.querySelector('.CodeMirror');
  if (cmEl) cmEl.style.fontSize = `${currentFontSize}px`;
  if (editor) editor.refresh();
}

btnFontInc.addEventListener('click', () => setFontSize(currentFontSize + 1));
btnFontDec.addEventListener('click', () => setFontSize(currentFontSize - 1));

// CodeMirror Setup
function initCodeMirror() {
  const textarea = document.getElementById('codeEditor');
  editor = CodeMirror.fromTextArea(textarea, {
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
      "Tab": function(cm) {
        if (cm.somethingSelected()) {
          cm.indentSelection("add");
        } else {
          cm.replaceSelection("    ", "end");
        }
      }
    }
  });

  setFontSize(15);

  // Editor events
  editor.on('change', (cm, changeObj) => {
    if (isRemoteChange || changeObj.origin === 'remote') return;
    
    let c = changeObj;
    while (c) {
      sendWsMessage({
        type: 'code_delta',
        from: c.from,
        to: c.to,
        text: c.text
      });
      c = c.next;
    }
    handleTyping();
  });

  editor.on('cursorActivity', (cm) => {
    if (isRemoteChange) return;
    const doc = cm.getDoc();
    const cursor = doc.getCursor();
    const selection = {
      anchor: doc.getCursor('anchor'),
      head: doc.getCursor('head')
    };
    sendWsMessage({
      type: 'cursor_change',
      cursor: cursor,
      selection: selection
    });
  });
}

function handleTyping() {
  sendWsMessage({ type: 'typing', is_typing: true });
  clearTimeout(typingTimeout);
  typingTimeout = setTimeout(() => {
    sendWsMessage({ type: 'typing', is_typing: false });
  }, 1000);
}

// Network Info
async function fetchAppInfo() {
  try {
    const res = await fetch('/api/info');
    const data = await res.json();
    
    lanIpText.textContent = `${data.ip}:${data.port}`;
    txtLanUrl.value = data.lan_url;
    imgQrCode.src = data.qr_code;
    palette = data.palette || [];
    claimedColors = data.claimed_colors || {};
    
    populateAllowedUsers(data.allowed_users || []);
    renderColorGrid();
  } catch (err) {
    lanIpText.textContent = 'Offline / Localhost';
  }
}

let activeUsersList = [];

const customUsernameGroup = document.getElementById('customUsernameGroup');
const txtCustomUsername = document.getElementById('txtCustomUsername');

function populateAllowedUsers(allowedUsers) {
  const selectedVal = selUsername.value;
  selUsername.innerHTML = '<option value="" disabled selected>-- Choose your name --</option>';
  
  const activeUsernames = activeUsersList.map(u => u.username ? u.username.toLowerCase() : '');

  allowedUsers.forEach(user => {
    const isTaken = activeUsernames.includes(user.toLowerCase()) && user !== currentUser;
    const opt = document.createElement('option');
    opt.value = user;
    opt.textContent = isTaken ? `${user} (Currently Logged In)` : user;
    if (isTaken) opt.disabled = true;
    selUsername.appendChild(opt);
  });

  // Guest / Custom Name option
  const guestOpt = document.createElement('option');
  guestOpt.value = '__custom__';
  guestOpt.textContent = '✨ Other / Join as Guest (Type Name)...';
  selUsername.appendChild(guestOpt);

  if (selectedVal) {
    selUsername.value = selectedVal;
  }
}

function renderColorGrid() {
  colorGrid.innerHTML = '';
  palette.forEach(color => {
    const isClaimed = claimedColors[color] && claimedColors[color] !== currentUser;
    const box = document.createElement('div');
    box.className = `color-option ${isClaimed ? 'claimed' : ''} ${currentColor === color ? 'selected' : ''}`;
    box.style.backgroundColor = color;
    box.title = isClaimed ? `Claimed by ${claimedColors[color]}` : color;

    if (!isClaimed) {
      box.addEventListener('click', () => {
        document.querySelectorAll('.color-option').forEach(el => el.classList.remove('selected'));
        box.classList.add('selected');
        currentColor = color;
        checkLoginValidity();
      });
    }

    colorGrid.appendChild(box);
  });
}

selUsername.addEventListener('change', () => {
  if (selUsername.value === '__custom__') {
    customUsernameGroup.style.display = 'block';
    txtCustomUsername.focus();
  } else {
    customUsernameGroup.style.display = 'none';
  }
  checkLoginValidity();
});

txtCustomUsername.addEventListener('input', checkLoginValidity);

function getEnteredUsername() {
  if (selUsername.value === '__custom__') {
    return txtCustomUsername.value.trim();
  }
  return selUsername.value.trim();
}

function checkLoginValidity() {
  const enteredName = getEnteredUsername();
  const activeUsernames = activeUsersList.map(u => u.username ? u.username.toLowerCase() : '');
  const isTaken = activeUsernames.includes(enteredName.toLowerCase()) && enteredName.toLowerCase() !== (currentUser || '').toLowerCase();
  
  const hasUser = enteredName.length > 0 && !isTaken;
  const hasColor = currentColor !== null;
  
  btnSubmitLogin.disabled = !(hasUser && hasColor);
}

frmLogin.addEventListener('submit', (e) => {
  e.preventDefault();
  const enteredName = getEnteredUsername();
  if (!enteredName || !currentColor) return;

  currentUser = enteredName;

  // Send Join over WebSocket
  sendWsMessage({
    type: 'join',
    username: currentUser,
    color: currentColor
  });

  // Update UI Profile
  myAvatar.style.backgroundColor = currentColor;
  myAvatar.textContent = currentUser.charAt(0).toUpperCase();
  myUsername.textContent = currentUser;
  userProfileBadge.style.display = 'flex';

  dlgLogin.close();
});

btnSwitchUser.addEventListener('click', () => {
  dlgLogin.showModal();
});

// WebSocket Sync
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/${clientId}`;

  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    wsStatus.className = 'status-indicator connected';
    wsStatusText.textContent = 'Connected';
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleWsMessage(data);
  };

  socket.onclose = () => {
    wsStatus.className = 'status-indicator';
    wsStatusText.textContent = 'Reconnecting...';
    setTimeout(initWebSocket, 2000);
  };

  socket.onerror = (err) => {
    console.error('WS Error:', err);
  };
}

function sendWsMessage(msg) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(msg));
  }
}

function handleWsMessage(data) {
  switch (data.type) {
    case 'init':
      if (data.code !== undefined && editor.getValue() !== data.code) {
        isRemoteChange = true;
        editor.setValue(data.code);
        isRemoteChange = false;
      }
      claimedColors = data.claimed_colors || {};
      palette = data.palette || palette;
      if (data.allowed_users) populateAllowedUsers(data.allowed_users);
      renderColorGrid();
      updatePresenceList(data.active_users || []);

      // Show login dialog if user not set
      if (!currentUser) {
        dlgLogin.showModal();
      }
      break;

    case 'user_joined':
      claimedColors = data.claimed_colors || {};
      renderColorGrid();
      updatePresenceList(data.active_users || []);
      break;

    case 'user_left':
      claimedColors = data.claimed_colors || {};
      renderColorGrid();
      updatePresenceList(data.active_users || []);
      removeRemoteCursor(data.id);
      break;

    case 'code_delta':
      if (!data.from || !data.to || !data.text) break;
      isRemoteChange = true;
      editor.operation(() => {
        editor.replaceRange(data.text, data.from, data.to, 'remote');
      });
      isRemoteChange = false;
      break;

    case 'code_update':
      isRemoteChange = true;
      const scrollInfo = editor.getScrollInfo();
      const cursor = editor.getCursor();
      editor.setValue(data.code);
      editor.scrollTo(scrollInfo.left, scrollInfo.top);
      editor.setCursor(cursor);
      isRemoteChange = false;
      break;

    case 'cursor_update':
      renderRemoteCursor(data);
      break;

    case 'typing_update':
      updateTypingBanner(data);
      break;

    case 'allowed_users_updated':
      populateAllowedUsers(data.allowed_users);
      break;

    case 'chat_history':
      chatHistoryList = data.messages || [];
      renderDmConversationsList();
      renderChatMessages();
      break;

    case 'chat_message':
      if (data.message) {
        chatHistoryList.push(data.message);
        renderDmConversationsList();
        renderChatMessages();
        const isFromOther = data.message.sender !== currentUser;
        
        if (isFromOther && data.message.target !== 'group') {
          // Show floating DM toast notification
          showDmNotification(data.message);
          
          if (isChatCollapsed || currentChatTab !== 'private' || activeDmRecipient !== data.message.sender) {
            unreadCount++;
            updateUnreadBadge();
          } else {
            // Automatically mark read if currently chatting with this user
            sendWsMessage({ type: 'mark_read', target: data.message.sender });
          }
        } else if (isFromOther && isChatCollapsed) {
          unreadCount++;
          updateUnreadBadge();
        }
      }
      break;

    case 'snapshot_created':
      // Flash snapshot notification
      break;

    case 'error':
      alert(data.message);
      break;
  }
}

// Remote Cursors Rendering
function renderRemoteCursor(data) {
  const { id, username, color, cursor } = data;
  if (!cursor || !username) return;

  removeRemoteCursor(id);

  const cursorEl = document.createElement('div');
  cursorEl.className = 'remote-cursor';
  cursorEl.style.borderColor = color;

  const flagEl = document.createElement('div');
  flagEl.className = 'remote-cursor-flag';
  flagEl.style.backgroundColor = color;
  flagEl.textContent = username;
  cursorEl.appendChild(flagEl);

  const marker = editor.setBookmark({ line: cursor.line, ch: cursor.ch }, {
    widget: cursorEl,
    insertLeft: true
  });

  remoteCursors[id] = marker;
}

function removeRemoteCursor(id) {
  if (remoteCursors[id]) {
    remoteCursors[id].clear();
    delete remoteCursors[id];
  }
}

function updatePresenceList(activeUsers) {
  activeUsersList = activeUsers || [];
  avatarGroup.innerHTML = '';
  lstActiveAdmin.innerHTML = '';

  const label = presenceBar.querySelector('.presence-label');
  label.textContent = `Active (${activeUsers.length}):`;

  activeUsers.forEach(u => {
    if (!u.username) return;
    const pill = document.createElement('div');
    pill.className = 'user-pill';
    pill.style.backgroundColor = u.color || '#3B82F6';
    pill.innerHTML = `
      <span>${u.username}</span>
      ${u.is_typing ? '<span class="typing-indicator"></span>' : ''}
    `;
    avatarGroup.appendChild(pill);

    // Admin modal active list
    const li = document.createElement('li');
    li.innerHTML = `<strong style="color:${u.color}">${u.username}</strong> - Active`;
    lstActiveAdmin.appendChild(li);
  });
}

function updateTypingBanner(data) {
  const typingUsers = [];
  if (data.is_typing) {
    typingBannerText.textContent = `${data.username} is editing live...`;
    typingBanner.style.display = 'flex';
  } else {
    typingBanner.style.display = 'none';
  }
}

// Code Execution Runner
btnRunCode.addEventListener('click', async () => {
  const code = editor.getValue();
  consoleOutput.className = 'console-output';
  consoleOutput.textContent = 'Executing Python code on server...';
  execTimeTag.style.display = 'none';
  outputDrawer.classList.remove('minimized');
  iconDrawerChevron.setAttribute('data-lucide', 'chevron-down');
  lucide.createIcons();

  sendWsMessage({ type: 'code_run_notice' });

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });

    const data = await res.json();
    execTimeTag.textContent = `${data.elapsed}s`;
    execTimeTag.style.display = 'inline-block';

    if (data.stderr) {
      consoleOutput.className = 'console-output stderr';
      consoleOutput.textContent = data.stderr + (data.stdout ? '\n' + data.stdout : '');
    } else {
      consoleOutput.className = 'console-output';
      consoleOutput.textContent = data.stdout || '(Code executed cleanly with no output)';
    }
  } catch (err) {
    consoleOutput.className = 'console-output stderr';
    consoleOutput.textContent = 'Failed to execute code: ' + err.message;
  }
});

// Output Console Toggles
btnClearOutput.addEventListener('click', () => {
  consoleOutput.textContent = '';
  execTimeTag.style.display = 'none';
});

btnToggleOutput.addEventListener('click', () => {
  outputDrawer.classList.toggle('minimized');
  const isMin = outputDrawer.classList.contains('minimized');
  iconDrawerChevron.setAttribute('data-lucide', isMin ? 'chevron-up' : 'chevron-down');
  lucide.createIcons();
});

// Modals Interaction
btnShowQr.addEventListener('click', () => dlgQr.showModal());
lanBadge.addEventListener('click', () => dlgQr.showModal());
btnCloseQr.addEventListener('click', () => dlgQr.close());

btnCopyLanUrl.addEventListener('click', () => {
  navigator.clipboard.writeText(txtLanUrl.value);
  btnCopyLanUrl.innerHTML = '<i data-lucide="check"></i> Copied!';
  lucide.createIcons();
  setTimeout(() => {
    btnCopyLanUrl.innerHTML = '<i data-lucide="copy"></i> Copy';
    lucide.createIcons();
  }, 2000);
});

btnCopyCode.addEventListener('click', () => {
  navigator.clipboard.writeText(editor.getValue());
  btnCopyCode.innerHTML = '<i data-lucide="check"></i> Copied!';
  lucide.createIcons();
  setTimeout(() => {
    btnCopyCode.innerHTML = '<i data-lucide="copy"></i> Copy Code';
    lucide.createIcons();
  }, 2000);
});

// Admin Panel Logic
btnAdmin.addEventListener('click', () => dlgAdmin.showModal());
btnCloseAdmin.addEventListener('click', () => dlgAdmin.close());

btnVerifyPin.addEventListener('click', () => {
  const pin = txtAdminPin.value.trim();
  if (pin === '1234') { // Default PIN
    adminAuthSec.style.display = 'none';
    adminContentSec.style.display = 'block';
    loadAdminUsers();
  } else {
    alert('Incorrect Admin PIN.');
  }
});

async function loadAdminUsers() {
  const res = await fetch('/api/users');
  const data = await res.json();
  txtAllowedUsers.value = (data.allowed_users || []).join('\n');
}

btnSaveAdminUsers.addEventListener('click', async () => {
  const lines = txtAllowedUsers.value.split('\n');
  const res = await fetch('/api/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      allowed_users: lines,
      admin_pin: txtAdminPin.value.trim()
    })
  });
  if (res.ok) {
    alert('Allowed usernames list updated!');
    dlgAdmin.close();
  }
});

// Snapshots Logic
btnSnapshots.addEventListener('click', () => {
  loadSnapshots();
  dlgSnapshots.showModal();
});
btnCloseSnapshots.addEventListener('click', () => dlgSnapshots.close());

btnSaveSnapshot.addEventListener('click', async () => {
  const label = prompt('Enter a label for this snapshot (e.g. "Exercise 1 Completed"):', 'Snapshot ' + new Date().toLocaleTimeString());
  if (!label) return;

  await fetch('/api/snapshots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      label: label,
      code: editor.getValue(),
      author: currentUser || 'Anonymous'
    })
  });
  alert('Snapshot saved successfully!');
});

async function loadSnapshots() {
  const res = await fetch('/api/snapshots');
  const data = await res.json();
  snapshotsList.innerHTML = '';

  if (!data.snapshots || data.snapshots.length === 0) {
    snapshotsList.innerHTML = '<p class="empty-state">No saved snapshots yet.</p>';
    return;
  }

  data.snapshots.forEach(s => {
    const card = document.createElement('div');
    card.className = 'snapshot-card';
    card.innerHTML = `
      <div class="snapshot-info">
        <h4>${s.label}</h4>
        <div class="snapshot-meta">Saved by <strong>${s.author}</strong> at ${s.timestamp}</div>
      </div>
      <button class="btn btn-secondary btn-sm btn-restore">Restore Code</button>
    `;

    card.querySelector('.btn-restore').addEventListener('click', () => {
      if (confirm(`Restore snapshot "${s.label}" to the live editor?`)) {
        editor.setValue(s.code);
        dlgSnapshots.close();
      }
    });

    snapshotsList.appendChild(card);
  });
}

// Chat Sidebar & DM Controller
const chatSidebar = document.getElementById('chatSidebar');
const chatResizeHandle = document.getElementById('chatResizeHandle');
const btnToggleChatBar = document.getElementById('btnToggleChatBar');
const btnCollapseChat = document.getElementById('btnCollapseChat');
const btnMinimizeChat = document.getElementById('btnMinimizeChat');
const chatUnreadBadge = document.getElementById('chatUnreadBadge');

const tabGroupChat = document.getElementById('tabGroupChat');
const tabPrivateChat = document.getElementById('tabPrivateChat');
const dmSubSidebar = document.getElementById('dmSubSidebar');
const dmConversationsList = document.getElementById('dmConversationsList');
const btnNewDm = document.getElementById('btnNewDm');
const dmSelectorBox = document.getElementById('dmSelectorBox');
const selDmRecipient = document.getElementById('selDmRecipient');

const chatMessagesContainer = document.getElementById('chatMessagesContainer');
const frmChat = document.getElementById('frmChat');
const txtChatMessage = document.getElementById('txtChatMessage');
const btnAttachFile = document.getElementById('btnAttachFile');

let isChatCollapsed = localStorage.getItem('chat_collapsed') === 'true';
let currentChatTab = 'group'; // 'group' or 'private'
let activeDmRecipient = null; // currently selected DM partner
let chatHistoryList = [];
let unreadCount = 0;

// Load & restore saved panel width
let savedWidth = parseInt(localStorage.getItem('chat_sidebar_width') || '420', 10);
if (savedWidth && savedWidth >= 320 && savedWidth <= 700) {
  if (window.innerWidth >= 768) {
    chatSidebar.style.width = `${savedWidth}px`;
  }
}

// Drag-to-Resize Sidebar Width Hook
let isDraggingResize = false;

if (chatResizeHandle) {
  chatResizeHandle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    isDraggingResize = true;
    chatSidebar.classList.add('is-resizing');
    chatResizeHandle.classList.add('active');
    document.body.classList.add('is-resizing');

    const handleMouseMove = (moveEvent) => {
      if (!isDraggingResize) return;
      const newWidth = window.innerWidth - moveEvent.clientX;
      if (newWidth >= 320 && newWidth <= 700) {
        chatSidebar.style.width = `${newWidth}px`;
        localStorage.setItem('chat_sidebar_width', newWidth);
      }
    };

    const handleMouseUp = () => {
      isDraggingResize = false;
      chatSidebar.classList.remove('is-resizing');
      chatResizeHandle.classList.remove('active');
      document.body.classList.remove('is-resizing');
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  });
}

// Auto-Growing Textarea & Enter (Send) vs Shift+Enter (New line)
if (txtChatMessage) {
  txtChatMessage.addEventListener('input', () => {
    txtChatMessage.style.height = 'auto';
    txtChatMessage.style.height = `${Math.min(txtChatMessage.scrollHeight, 120)}px`;
  });

  txtChatMessage.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      frmChat.dispatchEvent(new Event('submit'));
    }
  });
}

if (btnAttachFile) {
  btnAttachFile.addEventListener('click', () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.onchange = (e) => {
      const file = e.target.files[0];
      if (file) {
        txtChatMessage.value += ` [Attachment: ${file.name}]`;
        txtChatMessage.dispatchEvent(new Event('input'));
      }
    };
    fileInput.click();
  });
}

// Global ESC key listener to close chat sidebar
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !isChatCollapsed) {
    isChatCollapsed = true;
    localStorage.setItem('chat_collapsed', true);
    chatSidebar.classList.add('collapsed');
  }
});

// Formatting Preview (5 words max + ...)
function formatMessagePreview(text) {
  if (!text) return '';
  const words = text.trim().split(/\s+/);
  if (words.length <= 5) {
    return text.trim();
  }
  return words.slice(0, 5).join(' ') + '...';
}

// Floating DM Toast Notification
function showDmNotification(msg) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const previewText = formatMessagePreview(msg.text);

  const toast = document.createElement('div');
  toast.className = 'toast-card';
  toast.innerHTML = `
    <div class="toast-avatar" style="background-color: ${msg.color || '#38BDF8'}">
      ${(msg.sender || 'U').charAt(0).toUpperCase()}
    </div>
    <div class="toast-body">
      <div class="toast-header">
        <span class="toast-sender">${msg.sender}</span>
        <span class="toast-tag">🔒 DM</span>
      </div>
      <div class="toast-text">${escapeHtml(previewText)}</div>
    </div>
  `;

  toast.addEventListener('click', () => {
    // Expand chat sidebar if collapsed
    if (isChatCollapsed) {
      isChatCollapsed = false;
      localStorage.setItem('chat_collapsed', false);
      chatSidebar.classList.remove('collapsed');
    }
    // Switch to DM tab
    currentChatTab = 'private';
    tabPrivateChat.classList.add('active');
    tabGroupChat.classList.remove('active');
    dmSubSidebar.style.display = 'flex';

    // Select this sender in DM list & open conversation
    activeDmRecipient = msg.sender;
    selDmRecipient.value = msg.sender;
    sendWsMessage({ type: 'mark_read', target: msg.sender });
    renderDmConversationsList();
    renderChatMessages();

    // Remove toast
    toast.remove();
  });

  container.appendChild(toast);

  // Auto-remove toast after 6 seconds
  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }
  }, 6000);
}

// Initialize Chat Sidebar State
if (isChatCollapsed) {
  chatSidebar.classList.add('collapsed');
}

btnToggleChatBar.addEventListener('click', () => {
  isChatCollapsed = !isChatCollapsed;
  localStorage.setItem('chat_collapsed', isChatCollapsed);
  chatSidebar.classList.toggle('collapsed', isChatCollapsed);
  if (!isChatCollapsed) {
    unreadCount = 0;
    updateUnreadBadge();
    txtChatMessage.focus();
  }
});

btnCollapseChat.addEventListener('click', () => {
  isChatCollapsed = true;
  localStorage.setItem('chat_collapsed', true);
  chatSidebar.classList.add('collapsed');
});

tabGroupChat.addEventListener('click', () => {
  currentChatTab = 'group';
  tabGroupChat.classList.add('active');
  tabPrivateChat.classList.remove('active');
  dmSubSidebar.style.display = 'none';
  renderChatMessages();
});

tabPrivateChat.addEventListener('click', () => {
  currentChatTab = 'private';
  tabPrivateChat.classList.add('active');
  tabGroupChat.classList.remove('active');
  dmSubSidebar.style.display = 'flex';
  updateDmRecipientDropdown();
  renderDmConversationsList();
  renderChatMessages();
});

btnNewDm.addEventListener('click', () => {
  dmSelectorBox.style.display = dmSelectorBox.style.display === 'none' ? 'block' : 'none';
  if (dmSelectorBox.style.display === 'block') {
    updateDmRecipientDropdown();
  }
});

selDmRecipient.addEventListener('change', () => {
  activeDmRecipient = selDmRecipient.value;
  dmSelectorBox.style.display = 'none';
  sendWsMessage({ type: 'mark_read', target: activeDmRecipient });
  renderDmConversationsList();
  renderChatMessages();
});

function updateDmRecipientDropdown() {
  const curRecipient = selDmRecipient.value;
  selDmRecipient.innerHTML = '<option value="" disabled selected>-- Select student to DM --</option>';
  
  activeUsersList.forEach(u => {
    if (!u.username || u.username === currentUser) return;
    const opt = document.createElement('option');
    opt.value = u.username;
    opt.textContent = u.username;
    selDmRecipient.appendChild(opt);
  });

  if (curRecipient && activeUsersList.some(u => u.username === curRecipient)) {
    selDmRecipient.value = curRecipient;
  }
}

function renderDmConversationsList() {
  dmConversationsList.innerHTML = '';

  if (!currentUser) return;

  // Extract all unique users with whom currentUser has exchanged DMs
  const dmMap = new Map(); // username -> { lastMsg, timestamp, unreadCount, color }

  chatHistoryList.forEach(m => {
    if (m.target === 'group') return;
    const otherUser = m.sender === currentUser ? m.target : m.sender;
    if (!otherUser || otherUser === currentUser) return;

    const isUnread = m.sender !== currentUser && (!m.read_by || !m.read_by.includes(currentUser));

    if (!dmMap.has(otherUser)) {
      dmMap.set(otherUser, {
        username: otherUser,
        color: m.color || '#38BDF8',
        lastMsg: m.text,
        timestamp: m.timestamp || '',
        unreadCount: isUnread ? 1 : 0
      });
    } else {
      const entry = dmMap.get(otherUser);
      entry.lastMsg = m.text;
      entry.timestamp = m.timestamp || entry.timestamp;
      if (m.sender !== currentUser) entry.color = m.color || entry.color;
      if (isUnread) entry.unreadCount++;
    }
  });

  // Ensure active Users without prior chat are also joinable
  activeUsersList.forEach(u => {
    if (u.username && u.username !== currentUser && !dmMap.has(u.username)) {
      dmMap.set(u.username, {
        username: u.username,
        color: u.color || '#38BDF8',
        lastMsg: 'Click to open DM',
        timestamp: '',
        unreadCount: 0
      });
    }
  });

  if (dmMap.size === 0) {
    dmConversationsList.innerHTML = '<div class="dm-empty-list">No recent DMs</div>';
    return;
  }

  // Convert to array and render
  const convList = Array.from(dmMap.values());

  convList.forEach(item => {
    const isOnline = activeUsersList.some(u => u.username === item.username);
    const isSelected = activeDmRecipient === item.username;
    const preview = formatMessagePreview(item.lastMsg);

    const div = document.createElement('div');
    div.className = `dm-item ${isSelected ? 'selected' : ''}`;
    div.innerHTML = `
      <div class="dm-avatar-box">
        <div class="dm-avatar" style="background-color: ${item.color}">${item.username.charAt(0).toUpperCase()}</div>
        <span class="status-dot-badge ${isOnline ? 'online' : 'offline'}" title="${isOnline ? 'Online' : 'Offline'}"></span>
      </div>
      <div class="dm-details">
        <div class="dm-row-top">
          <span class="dm-username">${escapeHtml(item.username)}</span>
          <span class="dm-time">${item.timestamp}</span>
        </div>
        <div class="dm-last-msg">${escapeHtml(preview)}</div>
      </div>
      ${item.unreadCount > 0 ? `<span class="dm-unread-pill">${item.unreadCount}</span>` : ''}
    `;

    div.addEventListener('click', () => {
      activeDmRecipient = item.username;
      selDmRecipient.value = item.username;
      sendWsMessage({ type: 'mark_read', target: item.username });
      renderDmConversationsList();
      renderChatMessages();
    });

    dmConversationsList.appendChild(div);
  });
}

function updateUnreadBadge() {
  if (unreadCount > 0 && isChatCollapsed) {
    chatUnreadBadge.textContent = unreadCount > 9 ? '9+' : unreadCount;
    chatUnreadBadge.style.display = 'inline-block';
  } else {
    chatUnreadBadge.style.display = 'none';
    unreadCount = 0;
  }
}

function renderChatMessages() {
  chatMessagesContainer.innerHTML = '';

  const targetDm = currentChatTab === 'private' ? activeDmRecipient : null;

  const filtered = chatHistoryList.filter(m => {
    if (currentChatTab === 'group') {
      return m.target === 'group';
    } else { // private
      if (m.target === 'group') return false;
      if (!targetDm) return false;
      const isSenderMe = m.sender === currentUser;
      const isRecipientMe = m.target === currentUser;
      return (isSenderMe && m.target === targetDm) || (isRecipientMe && m.sender === targetDm);
    }
  });

  if (filtered.length === 0) {
    const emptyState = document.createElement('div');
    emptyState.className = 'chat-empty-state';
    emptyState.innerHTML = `
      <i data-lucide="${currentChatTab === 'group' ? 'messages-square' : 'lock'}"></i>
      <p>${currentChatTab === 'group' ? 'Classroom Group Channel' : (targetDm ? `Private Chat with ${targetDm}` : 'Select a conversation above to start DM')}</p>
      <span>${currentChatTab === 'group' ? 'No group messages yet.' : 'Send a private message.'}</span>
    `;
    chatMessagesContainer.appendChild(emptyState);
    lucide.createIcons();
    return;
  }

  filtered.forEach(m => {
    const isOwn = m.sender === currentUser;
    const isPrivate = m.target !== 'group';

    const card = document.createElement('div');
    card.className = `chat-msg-card ${isOwn ? 'own' : 'other'} ${isPrivate ? 'private' : ''}`;

    card.innerHTML = `
      <div class="chat-msg-header">
        <span class="chat-sender-name" style="color: ${m.color || 'inherit'}">${isOwn ? 'You' : m.sender}</span>
        ${isPrivate ? `<span class="chat-badge-dm">🔒 DM</span>` : ''}
        <span class="chat-timestamp">${m.timestamp}</span>
      </div>
      <div class="chat-msg-bubble">${escapeHtml(m.text)}</div>
    `;

    chatMessagesContainer.appendChild(card);
  });

  chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

frmChat.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = txtChatMessage.value.trim();
  if (!text) return;

  if (!currentUser) {
    alert('Please log in first before sending messages.');
    dlgLogin.showModal();
    return;
  }

  let target = 'group';
  if (currentChatTab === 'private') {
    target = activeDmRecipient;
    if (!target) {
      alert('Please select a student from the Direct Messages conversation list.');
      return;
    }
  }

  sendWsMessage({
    type: 'chat_message',
    target: target,
    text: text
  });

  txtChatMessage.value = '';
  txtChatMessage.style.height = 'auto';
});

// Update DM recipient dropdown when presence list updates
const origUpdatePresenceList = updatePresenceList;
updatePresenceList = function(activeUsers) {
  origUpdatePresenceList(activeUsers);
  updateDmRecipientDropdown();
};

