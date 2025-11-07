// ============================================
// MIEDZIOWE KARTY - APP.JS
// Prosty, działający JavaScript bez modules
// ============================================

console.log('🃏 Miedziowe Karty - App loaded');

// ============================================
// UTILITIES
// ============================================

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);
const hide = (el) => el?.classList.add('hidden');
const show = (el) => el?.classList.remove('hidden');

// Storage
const storage = {
    get: (key) => {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : null;
        } catch {
            return null;
        }
    },
    set: (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch {
            return false;
        }
    },
    remove: (key) => localStorage.removeItem(key),
    clear: () => localStorage.clear()
};

// ============================================
// MODALS
// ============================================

class Modal {
    constructor(id) {
        this.overlay = $(`#${id}`);
        this.closeBtn = this.overlay?.querySelector('.modal-close');
        
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }
        
        // Zamknij modal przy kliknięciu w tło
        if (this.overlay) {
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) {
                    this.close();
                }
            });
        }
    }
    
    open() {
        if (this.overlay) {
            show(this.overlay);
            console.log('Modal opened:', this.overlay.id);
        }
    }
    
    close() {
        if (this.overlay) {
            hide(this.overlay);
            console.log('Modal closed:', this.overlay.id);
        }
    }
}

// ============================================
// AUTH SERVICE
// ============================================

const AuthService = {
    async login(username, password) {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (!res.ok) throw new Error('Login failed');
        
        const data = await res.json();
        storage.set('mk_token', data.access_token);
        storage.set('mk_user', { id: data.user_id, username: data.username });
        return data;
    },
    
    async register(username, password) {
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (!res.ok) throw new Error('Register failed');
        
        const data = await res.json();
        storage.set('mk_token', data.access_token);
        storage.set('mk_user', { id: data.user_id, username: data.username });
        return data;
    },
    
    async guest(name) {
        const res = await fetch('/api/auth/guest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        const data = await res.json();
        storage.set('mk_token', data.access_token);
        storage.set('mk_user', { id: data.user_id, username: data.username, is_guest: true });
        return data;
    },
    
    logout() {
        storage.remove('mk_token');
        storage.remove('mk_user');
        window.location.href = '/';
    },
    
    getUser() {
        return storage.get('mk_user');
    },
    
    getToken() {
        return storage.get('mk_token');
    },
    
    isAuthenticated() {
        return !!this.getToken();
    }
};

// ============================================
// LANDING PAGE
// ============================================

function initLanding() {
    console.log('🏠 Initializing Landing Page');
    
    // Modals
    const loginModal = new Modal('login-modal-overlay');
    const registerModal = new Modal('register-modal-overlay');
    const guestModal = new Modal('guest-modal-overlay');
    
    // Buttons to open modals
    const showLoginBtn = $('#show-login-btn');
    const showRegisterBtn = $('#show-register-btn');
    const heroGuestBtn = $('#hero-guest-btn');
    
    if (showLoginBtn) {
        showLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Opening login modal');
            loginModal.open();
        });
    }
    
    if (showRegisterBtn) {
        showRegisterBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Opening register modal');
            registerModal.open();
        });
    }
    
    if (heroGuestBtn) {
        heroGuestBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Opening guest modal');
            guestModal.open();
        });
    }
    
    // Login form
    const loginForm = $('#login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = $('#login-username').value;
            const password = $('#login-password').value;
            const errorEl = $('#login-error');
            
            hide(errorEl);
            
            try {
                await AuthService.login(username, password);
                window.location.href = '/dashboard.html';
            } catch (err) {
                errorEl.textContent = 'Nieprawidłowa nazwa użytkownika lub hasło';
                show(errorEl);
            }
        });
    }
    
    // Register form
    const registerForm = $('#register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = $('#register-username').value;
            const password = $('#register-password').value;
            const confirm = $('#register-password-confirm').value;
            const errorEl = $('#register-error');
            
            hide(errorEl);
            
            if (password !== confirm) {
                errorEl.textContent = 'Hasła nie są identyczne';
                show(errorEl);
                return;
            }
            
            if (username.length < 3) {
                errorEl.textContent = 'Nazwa użytkownika musi mieć minimum 3 znaki';
                show(errorEl);
                return;
            }
            
            try {
                await AuthService.register(username, password);
                window.location.href = '/dashboard.html';
            } catch (err) {
                errorEl.textContent = 'Błąd rejestracji. Spróbuj innej nazwy użytkownika.';
                show(errorEl);
            }
        });
    }
    
    // Guest form
    const guestForm = $('#guest-form');
    if (guestForm) {
        guestForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const name = $('#guest-name').value || null;
            const errorEl = $('#guest-error');
            
            hide(errorEl);
            
            try {
                await AuthService.guest(name);
                window.location.href = '/dashboard.html';
            } catch (err) {
                errorEl.textContent = 'Błąd logowania jako gość';
                show(errorEl);
            }
        });
    }
    
    // Switch between modals
    const switchToRegister = $('#switch-to-register');
    const switchToLogin = $('#switch-to-login');
    
    if (switchToRegister) {
        switchToRegister.addEventListener('click', (e) => {
            e.preventDefault();
            loginModal.close();
            registerModal.open();
        });
    }
    
    if (switchToLogin) {
        switchToLogin.addEventListener('click', (e) => {
            e.preventDefault();
            registerModal.close();
            loginModal.open();
        });
    }
    
    console.log('✅ Landing page initialized');
}

// ============================================
// DASHBOARD
// ============================================

function initDashboard() {
    console.log('🎮 Initializing Dashboard');
    
    // Check auth
    if (!AuthService.isAuthenticated()) {
        console.warn('Not authenticated, redirecting to home');
        window.location.href = '/';
        return;
    }
    
    const user = AuthService.getUser();
    console.log('User:', user);
    
    // Update user name
    $$('.user-name').forEach(el => {
        el.textContent = user.username;
    });
    
    const welcomeUserName = $('#welcome-user-name');
    if (welcomeUserName) {
        welcomeUserName.textContent = user.username;
    }
    
    // Logout button
    const logoutBtn = $('#logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            AuthService.logout();
        });
    }
    
    // Sidebar toggle
    const sidebarToggle = $('.sidebar-toggle');
    const sidebar = $('.sidebar');

    console.log('Sidebar toggle button:', sidebarToggle);
    console.log('Sidebar element:', sidebar);

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            sidebar.classList.toggle('open');
            console.log('Sidebar toggled! Open:', sidebar.classList.contains('open'));
        });
    } else {
        console.error('Sidebar toggle nie znaleziony!', {
            button: sidebarToggle,
            sidebar: sidebar
        });
    }
    if (window.innerWidth >= 1025) {
    sidebar.classList.add('open');
    }
    window.addEventListener('resize', () => {
    if (window.innerWidth >= 1025 && !sidebar.classList.contains('open')) {
        sidebar.classList.add('open');
    }
});
    
    // Tabs
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all tabs
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            $$('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active to clicked tab
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            const tabContent = $(`#tab-${tabId}`);
            
            if (tabContent) {
                tabContent.classList.add('active');
                console.log('Tab switched to:', tabId);
            }
        });
    });
    
    // Create lobby form
    const createLobbyForm = $('#create-lobby-form');
    if (createLobbyForm) {
        createLobbyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const data = {
                lobby_type: "66",
                player_count: parseInt($('#player-count')?.value || '4'),
                ranked: $('#ranked-checkbox')?.checked || false,
                password: $('#lobby-password').value || null
            };
            
            console.log('Creating lobby:', data);
            
            try {
                const res = await fetch('/api/lobby/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${AuthService.getToken()}`
                    },
                    body: JSON.stringify(data)
                });
                
                if (!res.ok) throw new Error('Failed to create lobby');
                
                const lobby = await res.json();
                console.log('Lobby created:', lobby);
                window.location.href = `/lobby.html?id=${lobby.id_gry}`;
            } catch (err) {
                console.error('Error creating lobby:', err);
                alert('Błąd tworzenia lobby. Sprawdź czy backend działa.');
            }
        });
    }
    // Filtry lobby
    function setupLobbyFilters() {
    const filterBtns = $$('.filter-btn');
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active from all
            filterBtns.forEach(b => b.classList.remove('active'));
            
            // Add active to clicked
            btn.classList.add('active');
            
            // Reload lobbies
            loadLobbies();
        });
    });
}
// Setup filters
setupLobbyFilters();

// Load lobbies on page load
setTimeout(loadLobbies, 500);

// Auto-refresh co 10 sekund
setInterval(loadLobbies, 10000);
    
    // Load lobbies - ULEPSZONA WERSJA
async function loadLobbies() {
    const grid = $('#lobbies-grid');
    const emptyState = $('#lobbies-empty');
    const refreshBtn = $('#refresh-lobbies-btn');
    
    if (!grid) return;
    
    // Pokaż loading
    grid.innerHTML = '<div class="loading-spinner">Ładowanie lobby...</div>';
    hide(emptyState);
    
    // Disable refresh button
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.textContent = '🔄 Ładowanie...';
    }
    
    try {
        const res = await fetch('/api/lobby/list', {
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            }
        });
        
        if (!res.ok) throw new Error('Failed to load lobbies');
        
        const lobbies = await res.json();
        console.log('Lobbies loaded:', lobbies.length);
        await cleanupEmptyLobbies(lobbies);
        
        // Filtruj według aktywnego filtra
        const activeFilter = $('.filter-btn.active')?.dataset?.filter || 'all';
        const filtered = filterLobbies(lobbies, activeFilter);
        
        if (filtered.length === 0) {
            show(emptyState);
            grid.innerHTML = '';
        } else {
            hide(emptyState);
            grid.innerHTML = filtered.map(lobby => createLobbyCard(lobby)).join('');
        }
    } catch (err) {
        console.error('Error loading lobbies:', err);
        grid.innerHTML = '<div class="error-message">❌ Błąd ładowania lobby. Sprawdź czy backend działa.</div>';
    } finally {
        // Re-enable refresh button
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.textContent = '🔄 Odśwież';
        }
    }
}

async function cleanupEmptyLobbies(lobbies) {
    const emptyLobbies = lobbies.filter(lobby => {
        const playerCount = lobby.slots.filter(s => s.typ !== 'pusty').length;
        return playerCount === 0;
    });
    
    if (emptyLobbies.length === 0) return;
    
    console.log(`Znaleziono ${emptyLobbies.length} pustych lobby. Usuwanie...`);
    
    for (const lobby of emptyLobbies) {
        try {
            await fetch(`/api/lobby/${lobby.id_gry}/cleanup`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${AuthService.getToken()}`
                }
            });
            console.log(`Usunięto puste lobby: ${lobby.id_gry}`);
        } catch (err) {
            console.error(`Błąd usuwania lobby ${lobby.id_gry}:`, err);
        }
    }
}

// Filtrowanie lobby
function filterLobbies(lobbies, filter) {
    if (filter === 'all') return lobbies;
    if (filter === 'ranked') return lobbies.filter(l => l.opcje?.rankingowa === true);
    if (filter === 'casual') return lobbies.filter(l => l.opcje?.rankingowa === false);
    return lobbies;
}

// Tworzenie karty lobby - ULEPSZONA
function createLobbyCard(lobby) {
    const playerCount = lobby.slots.filter(s => s.typ !== 'pusty').length;
    const maxPlayers = lobby.max_graczy;
    const isRanked = lobby.opcje?.rankingowa;
    const hasPassword = lobby.opcje?.haslo ? true : false;
    const gameMode = lobby.opcje?.tryb_gry || '4p';
    const isFull = playerCount >= maxPlayers;
    
    // Badge
    const badge = isRanked 
        ? '<span class="badge badge-ranked">🏆 Rankingowa</span>'
        : '<span class="badge badge-casual">🎮 Casual</span>';
    
    // Status
    const statusClass = isFull ? 'lobby-full' : 'lobby-open';
    const statusText = isFull ? 'Pełne' : 'Otwarte';
    
    // Password icon
    const lockIcon = hasPassword ? '🔒' : '';
    
    return `
        <div class="lobby-card ${statusClass}" data-lobby-id="${lobby.id_gry}">
            <div class="lobby-card-header">
                <div class="lobby-title">
                    <h3>${lobby.id} ${lockIcon}</h3>
                    ${badge}
                </div>
                <div class="lobby-status ${statusClass}">
                    ${statusText}
                </div>
            </div>
            
            <div class="lobby-card-body">
                <div class="lobby-info-row">
                    <span class="lobby-info-label">👥 Gracze:</span>
                    <span class="lobby-info-value">${playerCount}/${maxPlayers}</span>
                </div>
                <div class="lobby-info-row">
                    <span class="lobby-info-label">🎲 Tryb:</span>
                    <span class="lobby-info-value">${gameMode}</span>
                </div>
                <div class="lobby-info-row">
                    <span class="lobby-info-label">🃏 Gra:</span>
                    <span class="lobby-info-value">66</span>
                </div>
            </div>
            
            <div class="lobby-card-footer">
                <button 
                    class="btn ${isFull ? 'btn-secondary' : 'btn-primary'} btn-block"
                    onclick="joinLobby('${lobby.id_gry}')"
                    ${isFull ? 'disabled' : ''}
                >
                    ${isFull ? '❌ Pełne' : '▶️ Dołącz'}
                </button>
            </div>
        </div>
    `;
}

// Join lobby function - ULEPSZONA
window.joinLobby = async (id) => {
    try {
        // Najpierw sprawdź czy lobby ma hasło
        const checkRes = await fetch(`/api/lobby/${id}/join`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            }
        });
        
        const data = await checkRes.json();
        
        if (checkRes.status === 403) {
            // Wymaga hasła
            const password = prompt('To lobby jest chronione hasłem:');
            if (!password) return;
            
            // Próbuj ponownie z hasłem
            const retryRes = await fetch(`/api/lobby/${id}/join?password=${encodeURIComponent(password)}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${AuthService.getToken()}`
                }
            });
            
            if (!retryRes.ok) {
                alert('❌ Nieprawidłowe hasło!');
                return;
            }
        } else if (!checkRes.ok) {
            throw new Error(data.detail || 'Nie można dołączyć');
        }
        
        // Redirect do lobby
        window.location.href = `/lobby.html?id=${id}`;
    } catch (err) {
        console.error('Error joining lobby:', err);
        alert(`❌ ${err.message}`);
    }
};
    
    // Load lobbies on page load
    setTimeout(loadLobbies, 500);
    
    console.log('✅ Dashboard initialized');
    
}

// ============================================
// LOBBY PAGE
// ============================================

function initLobby() {
    console.log('🎮 Initializing Lobby Page');
    
    // Check auth
    if (!AuthService.isAuthenticated()) {
        console.warn('Not authenticated, redirecting to home');
        window.location.href = '/';
        return;
    }
    
    const user = AuthService.getUser();
    console.log('User:', user);
    
    // Update user name in header
    const headerUserName = $('#header-user-name');
    if (headerUserName) {
        headerUserName.textContent = user.username;
    }
    
    // Get lobby ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const lobbyId = urlParams.get('id');
    
    if (!lobbyId) {
        showError('Brak ID lobby w URL');
        return;
    }
    
    console.log('Lobby ID:', lobbyId);
    
    // Update lobby ID in header
    const lobbyIdEl = $('#lobby-id');
    if (lobbyIdEl) {
        lobbyIdEl.textContent = lobbyId;
    }
    
    // Load lobby data
    loadLobbyDetails(lobbyId);
    
    // Setup buttons
    setupLobbyButtons(lobbyId, user);
    
    // Setup chat
    setupChat(lobbyId, user);
    
    // Connect WebSocket (opcjonalnie - na razie bez)
    // connectLobbyWebSocket(lobbyId, user);
    
    // Auto-refresh co 3 sekundy
    setInterval(() => loadLobbyDetails(lobbyId), 3000);
    
    
    console.log('✅ Lobby initialized');
    
    // Global flag - wyłącz auto-leave gdy gra się rozpoczyna
    window.lobbyGameStarted = false;
    
    window.addEventListener('beforeunload', () => {
    const lobbyId = new URLSearchParams(window.location.search).get('id');
    
    // NIE wywołuj /leave jeśli gra się rozpoczęła
    if (window.lobbyGameStarted) {
        console.log('[beforeunload] Gra się rozpoczęła - pomijam auto-leave');
        return;
    }
    
    if (lobbyId && AuthService.isAuthenticated()) {
        fetch(`/api/lobby/${lobbyId}/leave`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            },
            keepalive: true
        }).catch(() => {});  // Ignoruj błędy
    }
});
}

// Load lobby details
async function loadLobbyDetails(lobbyId) {
    try {
        const res = await fetch(`/api/lobby/${lobbyId}`, {
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            }
        });
        
        if (!res.ok) {
            if (res.status === 404) {
                showError('Lobby nie istnieje lub zostało usunięte');
                return;
            }
            throw new Error('Failed to load lobby');
        }
        
        const lobby = await res.json();
        console.log('Lobby data:', lobby);
        
        // Update UI
        updateLobbyUI(lobby);
        
    } catch (err) {
        console.error('Error loading lobby:', err);
    }
}

// Update lobby UI
function updateLobbyUI(lobby) {
    const user = AuthService.getUser();
    
    // Update game info
    const gameModeEl = $('#game-mode');
    const gameTypeEl = $('#game-type');
    const hostNameEl = $('#host-name');
    
    if (gameModeEl) {
        gameModeEl.textContent = lobby.opcje?.tryb_gry || '4-osobowy';
    }
    
    if (gameTypeEl) {
        gameTypeEl.textContent = lobby.opcje?.rankingowa ? '🏆 Rankingowa' : '🎮 Casual';
    }
    
    // Find host
    const hostSlot = lobby.slots.find(s => s.is_host);
    if (hostNameEl && hostSlot) {
        hostNameEl.textContent = hostSlot.nazwa || '-';
    }
    
    // Update slots
    lobby.slots.forEach((slot, index) => {
        const slotEl = $(`#slot-${index}`);
        if (!slotEl) return;
        
        // Reset classes
        slotEl.className = 'player-slot';
        
        if (slot.typ === 'pusty') {
            // Empty slot
            slotEl.classList.add('empty');
            slotEl.innerHTML = `
                <div class="slot-number">${index + 1}</div>
                <div class="slot-content">
                    <div class="empty-slot-text">Puste miejsce</div>
                </div>
            `;
        } else {
            // Filled slot
            slotEl.classList.add('filled');
            
            if (slot.ready) slotEl.classList.add('ready');
            if (slot.is_host) slotEl.classList.add('host');
            if (slot.typ === 'bot') slotEl.classList.add('bot');
            
            const badges = [];
            if (slot.is_host) badges.push('<span class="player-badge badge-host">👑 Host</span>');
            if (slot.ready) badges.push('<span class="player-badge badge-ready">✅ Gotowy</span>');
            if (slot.typ === 'bot') badges.push('<span class="player-badge badge-bot">🤖 Bot</span>');
            
            const isCurrentUser = slot.id_uzytkownika === user.id;
            const canKick = lobby.is_host && !slot.is_host && (slot.typ === 'bot' || !isCurrentUser);
            
            slotEl.innerHTML = `
                <div class="slot-number">${index + 1}</div>
                <div class="slot-content">
                    <div class="player-info">
                        <div class="player-avatar">${slot.typ === 'bot' ? '🤖' : '👤'}</div>
                        <div class="player-name">${slot.nazwa}</div>
                        <div class="player-badges">
                            ${badges.join('')}
                        </div>
                        ${canKick ? `
                            <div class="player-actions">
                                <button class="btn btn-danger btn-sm" onclick="kickPlayer('${slot.id_uzytkownika}')">
                                    Wyrzuć
                                </button>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
    });
    
    // Update player count
    const playerCount = lobby.slots.filter(s => s.typ !== 'pusty').length;
    const playerCountEl = $('#player-count');
    if (playerCountEl) {
        playerCountEl.textContent = playerCount;
    }
    
    // Update buttons
    updateLobbyButtons(lobby);
}

// Update buttons based on lobby state
function updateLobbyButtons(lobby) {
    const user = AuthService.getUser();
    const readyBtn = $('#ready-btn');
    const startBtn = $('#start-btn');
    const addBotBtn = $('#add-bot-btn');
    
    const currentSlot = lobby.slots.find(s => s.id_uzytkownika === user.id);
    const isReady = currentSlot?.ready || false;
    const playerCount = lobby.slots.filter(s => s.typ !== 'pusty').length;
    const allReady = lobby.slots.every(s => s.typ === 'pusty' || s.typ === 'bot' || s.ready);
    
    // Ready button
    if (readyBtn) {
        readyBtn.disabled = false;
        readyBtn.textContent = isReady ? '❌ Anuluj gotowość' : '✅ Jestem gotowy';
        readyBtn.className = isReady ? 'btn btn-secondary btn-block' : 'btn btn-primary btn-block';
    }
    
    // Start button (tylko host)
    if (startBtn) {
        if (lobby.is_host) {
            show(startBtn);
            startBtn.disabled = playerCount < 3 || !allReady;
            startBtn.title = playerCount < 3 ? 'Potrzeba minimum 3 graczy' : (!allReady ? 'Nie wszyscy są gotowi' : 'Rozpocznij grę');
        } else {
            hide(startBtn);
        }
    }
    
    // Add bot button (tylko host)
    if (addBotBtn) {
        const hasEmptySlot = lobby.slots.some(s => s.typ === 'pusty');
        if (lobby.is_host && hasEmptySlot) {
            show(addBotBtn);
        } else {
            hide(addBotBtn);
        }
    }
}

// Setup buttons
function setupLobbyButtons(lobbyId, user) {
    const readyBtn = $('#ready-btn');
    const startBtn = $('#start-btn');
    const addBotBtn = $('#add-bot-btn');
    const leaveBtn = $('#leave-btn');
    
    // Ready button
    if (readyBtn) {
        readyBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`/api/lobby/${lobbyId}/ready`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${AuthService.getToken()}`
                    }
                });
                
                if (!res.ok) throw new Error('Failed to toggle ready');
                
                const data = await res.json();
                console.log('Ready toggled:', data.ready);
                
                // Reload lobby
                await loadLobbyDetails(lobbyId);
                
            } catch (err) {
                console.error('Error toggling ready:', err);
                alert('❌ Błąd zmiany gotowości');
            }
        });
    }
    
    // Start button
    if (startBtn) {
        startBtn.addEventListener('click', async () => {
            if (!confirm('Rozpocząć grę?')) return;
            
            try {
                const res = await fetch(`/api/lobby/${lobbyId}/start`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${AuthService.getToken()}`
                    }
                });
                
                if (!res.ok) {
                    const data = await res.json();
                    alert(`❌ ${data.detail}`);
                    return;
                }
                
                console.log('Game started!');
                
                // Ustaw flagę - wyłącz auto-leave
                window.lobbyGameStarted = true;
                
                // Przekieruj do ekranu gry
                window.location.href = `/game.html?id=${lobbyId}`;
                
            } catch (err) {
                console.error('Error starting game:', err);
                alert('❌ Błąd rozpoczynania gry');
            }
        });
    }
    
    // Add bot button
    if (addBotBtn) {
        addBotBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`/api/lobby/${lobbyId}/add-bot`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${AuthService.getToken()}`
                    }
                });
                
                if (!res.ok) throw new Error('Failed to add bot');
                
                const data = await res.json();
                console.log('Bot added:', data.bot);
                
                // Reload lobby
                await loadLobbyDetails(lobbyId);
                
            } catch (err) {
                console.error('Error adding bot:', err);
                alert('❌ Błąd dodawania bota');
            }
        });
    }
    
    // Leave button
    if (leaveBtn) {
        leaveBtn.addEventListener('click', async () => {
            if (!confirm('Opuścić lobby?')) return;
            
            try {
                const res = await fetch(`/api/lobby/${lobbyId}/leave`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${AuthService.getToken()}`
                    }
                });
                
                if (!res.ok) throw new Error('Failed to leave lobby');
                
                console.log('Left lobby');
                window.location.href = '/dashboard.html';
                
            } catch (err) {
                console.error('Error leaving lobby:', err);
                alert('❌ Błąd opuszczania lobby');
            }
        });
    }
}

// Kick player (global function)
window.kickPlayer = async function(userId) {
    if (!confirm('Wyrzucić tego gracza?')) return;
    
    const urlParams = new URLSearchParams(window.location.search);
    const lobbyId = urlParams.get('id');
    
    try {
        const res = await fetch(`/api/lobby/${lobbyId}/kick/${userId}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            }
        });
        
        if (!res.ok) throw new Error('Failed to kick player');
        
        console.log('Player kicked');
        await loadLobbyDetails(lobbyId);
        
    } catch (err) {
        console.error('Error kicking player:', err);
        alert('❌ Błąd wyrzucania gracza');
    }
};

// Setup chat
function setupChat(lobbyId, user) {
    const chatInput = $('#chat-input');
    const chatSendBtn = $('#chat-send-btn');
    const chatMessages = $('#chat-messages');
    
    const sendMessage = () => {
        const message = chatInput.value.trim();
        if (!message) return;
        
        // Add message to chat (local)
        const messageEl = document.createElement('div');
        messageEl.className = 'chat-message own';
        messageEl.innerHTML = `
            <div class="chat-author">${user.username}</div>
            <div class="chat-text">${message}</div>
        `;
        chatMessages.appendChild(messageEl);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Clear input
        chatInput.value = '';
        
        // TODO: Send via WebSocket
        console.log('Chat message:', message);
    };
    
    if (chatSendBtn) {
        chatSendBtn.addEventListener('click', sendMessage);
    }
    
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
}

// Show error modal
function showError(message) {
    const errorModal = $('#error-modal');
    const errorMessage = $('#error-message');
    
    if (errorMessage) {
        errorMessage.textContent = message;
    }
    
    if (errorModal) {
        show(errorModal);
    }
}


// ============================================
// GAME PAGE - Gra w 66
// ============================================

function initGame() {
    console.log('🎮 Initializing Game Page');
    
    // Check auth
    if (!AuthService.isAuthenticated()) {
        console.warn('Not authenticated, redirecting');
        window.location.href = '/';
        return;
    }
    
    const user = AuthService.getUser();
    console.log('User:', user);
    
    // Get game ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const gameId = urlParams.get('id');
    
    if (!gameId) {
        alert('Brak ID gry w URL');
        window.location.href = '/dashboard.html';
        return;
    }
    
    console.log('Game ID:', gameId);
    
    // Initialize game state
    window.gameState = {
        gameId: gameId,
        user: user,
        engineState: null,  // Stan z silnika
        yourPlayerId: user.username,
        finalizingTrick: false,
        lastFaza: null
    };
    
    // Setup UI
    setupGameUI();
    
    // Load game data
    loadGameState(gameId);
    
    // Setup buttons
    setupGameButtons();
    
    // Auto-refresh co 2 sekundy
    window.gameRefreshInterval = setInterval(() => {
        loadGameState(gameId);
    }, 2000);
    
    console.log('✅ Game initialized');
}

// Setup Game UI
function setupGameUI() {
    // Leave button
    const leaveBtn = $('#leave-game-btn');
    if (leaveBtn) {
        leaveBtn.addEventListener('click', () => {
            if (confirm('Opuścić grę?')) {
                clearInterval(window.gameRefreshInterval);
                window.location.href = '/dashboard.html';
            }
        });
    }
}

// Load Game State from Engine
async function loadGameState(gameId) {
    try {
        const res = await fetch(`/api/game/${gameId}/state`, {
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            }
        });
        
        if (!res.ok) {
            throw new Error('Failed to load game state');
        }
        
        const data = await res.json();
        console.log('Game state:', data);
        
        // Update global state
        window.gameState.engineState = data;
        
        // Sprawdź czy gra się zakończyła
        if (data.faza === 'PODSUMOWANIE_ROZDANIA' || data.faza === 'ZAKONCZONE') {
            console.log('🏁 Gra zakończona - zatrzymuję auto-refresh');
            if (window.gameRefreshInterval) {
                clearInterval(window.gameRefreshInterval);
                window.gameRefreshInterval = null;
            }
            showGameSummary(data);
        }
        
        // Render UI
        renderGameUI(data);
        
    } catch (err) {
        console.error('Error loading game:', err);
        // Nie pokazuj alertu - może być tymczasowy błąd
    }
}

// Render Game UI from Engine State
function renderGameUI(state) {
    if (!state) return;
    
    // Update header
    const roundEl = $('#round-number');
    if (roundEl) roundEl.textContent = '1'; // TODO: z silnika
    
    const currentPlayerName = state.kolej_gracza || '-';
    const playerNameEl = $('#current-player-name');
    if (playerNameEl) playerNameEl.textContent = currentPlayerName;
    
    // Jeśli gra się zakończyła, wyczyść stół i ręce
    if (state.faza === 'PODSUMOWANIE_ROZDANIA' || state.faza === 'ZAKONCZONE') {
        const playedEl = $('#played-cards');
        if (playedEl) playedEl.innerHTML = '';
        const handEl = $('#your-hand');
        if (handEl) handEl.innerHTML = '';
        return; // Nie renderuj nic więcej
    }
    
    // Render your hand
    renderYourHand(state);
    
    // Render played cards on table
    renderPlayedCards(state);
    
    // Update trump display
    if (state.kontrakt && state.kontrakt.atut) {
        updateTrumpDisplay(state.kontrakt.atut);
    }
    
    // Update scores
    updateScores(state);
    
    // Update phase info (tylko jeśli zmiana)
    if (state.faza && state.faza !== window.gameState.lastFaza) {
        addLog(`Faza: ${state.faza}`, 'info');
        window.gameState.lastFaza = state.faza;
    }
    
    // === POPRAWIONE: Automatyczna finalizacja lewy (tylko RAZ!) ===
    if (state.lewa_do_zamkniecia) {
        if (!window.gameState.finalizingTrick) {
            console.log('🎯 Lewa do zamknięcia - auto-finalizacja za 2s');
            window.gameState.finalizingTrick = true;
            addLog('Lewa zakończona - finalizacja...', 'success');
            
            setTimeout(() => {
                finalizeCurrentTrick();
            }, 2000);
        }
    } else {
        window.gameState.finalizingTrick = false;
    }
}

// === Finalizacja lewy ===
async function finalizeCurrentTrick() {
    try {
        const gameId = window.gameState.gameId;
        
        const res = await fetch(`/api/game/${gameId}/finalize-trick`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            }
        });
        
        if (!res.ok) {
            // Jeśli 400 - prawdopodobnie lewa już sfinalizowana
            console.log('⚠️ Finalizacja zwróciła błąd, odświeżam stan...');
            await loadGameState(gameId);
            return;
        }
        
        const data = await res.json();
        console.log('✅ Lewa sfinalizowana:', data);
        
        // Odśwież stan
        window.gameState.engineState = data.state;
        
        // Resetuj flagę finalizacji
        window.gameState.finalizingTrick = false;
        
        renderGameUI(data.state);
        
        addLog('Lewa zebrana!', 'success');
        
    } catch (err) {
        console.error('Error finalizing trick:', err);
        
        // Resetuj flagę finalizacji nawet przy błędzie
        window.gameState.finalizingTrick = false;
        
        // Odśwież stan
        try {
            await loadGameState(window.gameState.gameId);
        } catch (loadErr) {
            console.error('Nie można odświeżyć stanu:', loadErr);
        }
    }
}


// Render Your Hand (twoje karty)
function renderYourHand(state) {
    const handEl = $('#your-hand');
    if (!handEl) return;
    
    const yourPlayerId = window.gameState.yourPlayerId;
    
    // Pobierz twoje karty z rece_graczy
    const yourCards = state.rece_graczy?.[yourPlayerId];
    
    if (!Array.isArray(yourCards)) {
        console.log('Brak kart gracza lub nie jesteś w grze');
        return;
    }
    
    // Wyczyść
    handEl.innerHTML = '';
    
    // Czy twoja tura?
    const isYourTurn = state.kolej_gracza === yourPlayerId;
    const playableCards = state.grywalne_karty || [];
    
    yourCards.forEach((cardName) => {
        const cardEl = createCardFromString(cardName);
        
        // Sprawdź czy można zagrać
        const isPlayable = isYourTurn && playableCards.includes(cardName);
        
        if (isPlayable) {
            cardEl.classList.add('playable');
            cardEl.onclick = () => playCard(cardName);
        } else {
            cardEl.classList.add('disabled');
        }
        
        handEl.appendChild(cardEl);
    });
}

// Render Played Cards (karty na stole)
function renderPlayedCards(state) {
    const playedEl = $('#played-cards');
    if (!playedEl) return;
    
    playedEl.innerHTML = '';
    
    const cardsOnTable = state.karty_na_stole || [];
    
    cardsOnTable.forEach((item) => {
        const cardEl = createCardFromString(item.karta);
        cardEl.classList.add('played-card');
        
        // Dodaj label gracza
        const playerLabel = document.createElement('div');
        playerLabel.textContent = item.gracz;
        playerLabel.style.cssText = 'font-size: 10px; text-align: center; color: white; margin-top: 4px;';
        
        const wrapper = document.createElement('div');
        wrapper.appendChild(cardEl);
        wrapper.appendChild(playerLabel);
        
        playedEl.appendChild(wrapper);
    });
}

// Create Card Element from String (np. "As Czerwien")
function createCardFromString(cardName) {
    const div = document.createElement('div');
    div.className = 'card';
    
    // Parse card name (np. "As Czerwien")
    const parts = cardName.split(' ');
    const rank = parts[0];
    const suitName = parts[1];
    
    // Map suit names to symbols
    const suitMap = {
        'Czerwien': '♥',
        'Dzwonek': '♦',
        'Zoladz': '♣',
        'Wino': '♠'
    };
    
    const suitSymbol = suitMap[suitName] || '?';
    
    // Map suit to English for CSS class
    const suitClassMap = {
        'Czerwien': 'hearts',
        'Dzwonek': 'diamonds',
        'Zoladz': 'clubs',
        'Wino': 'spades'
    };
    
    const suitClass = suitClassMap[suitName] || 'hearts';
    
    // Map rank names
    const rankMap = {
        'As': 'A',
        'Dziesiatka': '10',
        'Krol': 'K',
        'Dama': 'Q',
        'Walet': 'J',
        'Dziewiatka': '9'
    };
    
    const rankDisplay = rankMap[rank] || rank;
    
    div.dataset.suit = suitClass;
    div.dataset.rank = rankDisplay;
    
    div.innerHTML = `
        <div class="card-content">
            <div class="card-corner top-left">
                <span class="rank">${rankDisplay}</span>
                <span class="suit">${suitSymbol}</span>
            </div>
            <div class="card-center">
                <span class="suit-big">${suitSymbol}</span>
            </div>
            <div class="card-corner bottom-right">
                <span class="rank">${rankDisplay}</span>
                <span class="suit">${suitSymbol}</span>
            </div>
        </div>
    `;
    
    return div;
}

// Play Card (zagraj kartę)
async function playCard(cardName) {
    console.log('Playing card:', cardName);
    
    const state = window.gameState.engineState;
    
    if (!state || state.kolej_gracza !== window.gameState.yourPlayerId) {
        addLog('To nie Twoja tura!', 'info');
        return;
    }
    
    try {
        const res = await fetch(`/api/game/${window.gameState.gameId}/play`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${AuthService.getToken()}`
            },
            body: JSON.stringify({
                typ: 'zagraj_karte',
                karta: cardName
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to play card');
        }
        
        const data = await res.json();
        console.log('Card played:', data);
        
        // Update state
        window.gameState.engineState = data.state;
        renderGameUI(data.state);
        
        addLog(`Zagrałeś ${cardName}`, 'success');
        
        // Odśwież po chwili (żeby zobaczyć odpowiedź botów)
        setTimeout(() => loadGameState(window.gameState.gameId), 500);
        
    } catch (err) {
        console.error('Error playing card:', err);
        alert(err.message);
    }
}

// Update Trump Display
function updateTrumpDisplay(atut) {
    const trumpEl = $('#trump-suit');
    if (!trumpEl) return;
    
    const suitMap = {
        'CZERWIEN': '♥',
        'DZWONEK': '♦',
        'ZOLADZ': '♣',
        'WINO': '♠'
    };
    
    trumpEl.textContent = suitMap[atut] || '?';
}

// Update Scores
function updateScores(state) {
    const punkty = state.punkty_w_rozdaniu || {};
    
    // TODO: Mapowanie drużyn na graczy
    // Na razie wyświetl podstawowe info
    console.log('Punkty:', punkty);
}

// Add Log Message
function addLog(message, type = '') {
    const logEl = $('#log-messages');
    if (!logEl) return;
    
    const msgEl = document.createElement('div');
    msgEl.className = `log-message ${type}`;
    msgEl.textContent = message;
    
    logEl.appendChild(msgEl);
    logEl.scrollTop = logEl.scrollHeight;
    
    // Limit do 50 wiadomości
    while (logEl.children.length > 50) {
        logEl.removeChild(logEl.firstChild);
    }
}

// Setup Game Buttons
function setupGameButtons() {
    // Additional button setup if needed
}

// ============================================
// GAME SUMMARY MODAL
// ============================================

function showGameSummary(state) {
    console.log('🏆 Pokazuję podsumowanie:', state.podsumowanie);
    console.log('🎮 Cały stan:', state);
    
    if (!state.podsumowanie) {
        console.warn('Brak danych podsumowania - używam danych ze stanu');
    }
    
    const summary = state.podsumowanie || {};
    
    // Usuń stary modal jeśli istnieje
    const oldModal = $('#game-summary-modal');
    if (oldModal) oldModal.remove();
    
    // Stwórz modal
    const modal = document.createElement('div');
    modal.id = 'game-summary-modal';
    modal.className = 'modal-overlay';
    modal.style.cssText = `
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;
    
    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.cssText = `
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 40px;
        border-radius: 20px;
        max-width: 600px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        border: 2px solid rgba(255,255,255,0.1);
        text-align: center;
    `;
    
    const title = document.createElement('h2');
    title.textContent = '🏆 Koniec Rozdania';
    title.style.cssText = 'color: #fff; margin-bottom: 30px; font-size: 32px;';
    
    // Zwycięzca - sprawdź różne źródła danych
    const winner = document.createElement('div');
    winner.style.cssText = 'font-size: 24px; color: #4ade80; margin-bottom: 20px; font-weight: bold;';
    
    const zwyciezca = summary.zwyciezca || 
                     summary.druzyna_wygrana || 
                     (state.zwyciezca_rozdania ? state.zwyciezca_rozdania.nazwa : null) ||
                     'Nierozstrzygnięte';
    winner.textContent = `Zwycięzca: ${zwyciezca}`;
    
    // Punkty - pobierz z różnych źródeł
    const punktyRozdania = summary.punkty_rozdania || state.punkty_w_rozdaniu || {};
    const punktyMeczu = summary.punkty_meczu || {};
    
    // Jeśli punkty_meczu są puste, spróbuj z drużyn
    if (Object.keys(punktyMeczu).length === 0 && state.druzyny) {
        state.druzyny.forEach(druzyna => {
            punktyMeczu[druzyna.nazwa] = druzyna.punkty_meczu || 0;
        });
    }
    
    const points = document.createElement('div');
    points.style.cssText = 'background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; margin: 20px 0;';
    
    let pointsHTML = '<div style="color: #fff; font-size: 18px; margin-bottom: 15px;"><strong>Punkty w rozdaniu:</strong></div>';
    if (Object.keys(punktyRozdania).length > 0) {
        pointsHTML += '<div style="color: #94a3b8; font-size: 16px; line-height: 1.8;">';
        Object.entries(punktyRozdania).forEach(([team, pts]) => {
            pointsHTML += `<div>${team}: <strong style="color: #fff">${pts} pkt</strong></div>`;
        });
        pointsHTML += '</div>';
    } else {
        pointsHTML += '<div style="color: #94a3b8; font-size: 14px;">Brak danych</div>';
    }
    
    pointsHTML += '<div style="margin-top: 20px; color: #fff; font-size: 18px;"><strong>Punkty meczu:</strong></div>';
    if (Object.keys(punktyMeczu).length > 0) {
        pointsHTML += '<div style="color: #94a3b8; font-size: 16px; line-height: 1.8;">';
        Object.entries(punktyMeczu).forEach(([team, pts]) => {
            pointsHTML += `<div>${team}: <strong style="color: #4ade80">${pts} pkt</strong></div>`;
        });
        pointsHTML += '</div>';
    } else {
        pointsHTML += '<div style="color: #94a3b8; font-size: 14px;">Brak danych</div>';
    }
    
    points.innerHTML = pointsHTML;
    
    // Przyciski
    const buttons = document.createElement('div');
    buttons.style.cssText = 'margin-top: 30px; display: flex; gap: 15px; justify-content: center;';
    
    // Sprawdź czy to koniec meczu (któraś drużyna ma >= 66 pkt)
    let maxPoints = 0;
    
    if (Object.keys(punktyMeczu).length > 0) {
        // Pobierz wartości punktów, odfiltruj nie-liczby
        const punktyValues = Object.values(punktyMeczu)
            .filter(p => typeof p === 'number' && !isNaN(p));
        
        if (punktyValues.length > 0) {
            maxPoints = Math.max(...punktyValues);
        }
    }
    
    const koniecMeczu = maxPoints >= 66;
    
    console.log('Punkty meczu:', punktyMeczu);
    console.log('Max punktów:', maxPoints, 'Koniec meczu:', koniecMeczu);
    
    // Przycisk "Następna runda" - tylko jeśli NIE koniec meczu
    if (!koniecMeczu) {
        const nextRoundBtn = document.createElement('button');
        nextRoundBtn.textContent = '▶️ Następna runda';
        nextRoundBtn.style.cssText = `
            padding: 15px 30px; font-size: 18px; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; cursor: pointer; font-weight: bold; transition: transform 0.2s;
        `;
        nextRoundBtn.onmouseover = () => nextRoundBtn.style.transform = 'scale(1.05)';
        nextRoundBtn.onmouseout = () => nextRoundBtn.style.transform = 'scale(1)';
        nextRoundBtn.onclick = () => { 
            modal.remove(); 
            startNextRound(); 
        };
        buttons.appendChild(nextRoundBtn);
    }
    
    // Przycisk "Wyjdź" - tylko jeśli KONIEC meczu
    if (koniecMeczu) {
        title.textContent = '🏆 KONIEC MECZU!';
        
        const leaveBtnModal = document.createElement('button');
        leaveBtnModal.textContent = '🚪 Wyjdź do Dashboard';
        leaveBtnModal.style.cssText = `
            padding: 15px 30px; font-size: 18px; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; cursor: pointer; font-weight: bold; transition: transform 0.2s;
        `;
        leaveBtnModal.onmouseover = () => leaveBtnModal.style.transform = 'scale(1.05)';
        leaveBtnModal.onmouseout = () => leaveBtnModal.style.transform = 'scale(1)';
        leaveBtnModal.onclick = () => {
            window.location.href = '/dashboard.html';
        };
        buttons.appendChild(leaveBtnModal);
    }
    
    // Złóż modal
    content.appendChild(title);
    content.appendChild(winner);
    content.appendChild(points);
    content.appendChild(buttons);
    modal.appendChild(content);
    document.body.appendChild(modal);
}

// Funkcja startująca następną rundę
async function startNextRound() {
    console.log('🔄 Rozpoczynam następną rundę...');
    addLog('Rozpoczynam następną rundę...', 'info');
    
    try {
        // Wywołaj endpoint do rozpoczęcia nowej rundy
        const res = await fetch(`/api/game/${window.gameState.gameId}/next-round`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${AuthService.getToken()}`
            }
        });
        
        if (res.ok) {
            console.log('✅ Nowa runda rozpoczęta');
            
            // === WAŻNE: Wznów auto-refresh! ===
            if (!window.gameRefreshInterval) {
                console.log('🔄 Wznawianie auto-refresh...');
                window.gameRefreshInterval = setInterval(() => {
                    loadGameState(window.gameState.gameId);
                }, 2000);
            }
            
            // Resetuj flagi
            window.gameState.finalizingTrick = false;
            window.gameState.lastFaza = null;
            
            // Odśwież stan NATYCHMIAST
            await loadGameState(window.gameState.gameId);
            
        } else {
            console.error('❌ Błąd rozpoczynania rundy');
            const error = await res.json().catch(() => ({}));
            console.error('Error:', error);
            alert('Nie można rozpocząć nowej rundy. Odśwież stronę.');
        }
    } catch (err) {
        console.error('Error starting next round:', err);
        alert('Błąd połączenia. Odśwież stronę.');
    }
}

// ============================================
// INITIALIZATION
// ============================================

// Run appropriate init based on page
if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
    initLanding();
} else if (window.location.pathname === '/dashboard.html') {
    initDashboard();
} else if (window.location.pathname === '/lobby.html') {
    initLobby();
} else if (window.location.pathname === '/game.html') {
    initGame();
}