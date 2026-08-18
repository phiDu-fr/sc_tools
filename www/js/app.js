let globalData = { speakers: {}, presets: {}, radios: [] };
let hasInitializedSpeakers = false;
let isFetchingState = false;

let selectedSpeakersOrder = [];
let isMultiSelectMode = false;
let longPressTimer;
let isPresetRecordMode = false;
const LONG_PRESS_DURATION = 500;

function handleSpeakerTouchStart(event, ip) {
    const spk = globalData.speakers[ip];
    if (!spk || (spk.state !== 'ON' && spk.state !== 'STANDBY')) return;

    longPressTimer = setTimeout(() => {
        isMultiSelectMode = true;
        if (navigator.vibrate) navigator.vibrate(50); 
        toggleSpeakerSelection(ip);
    }, LONG_PRESS_DURATION);
}

function handleSpeakerTouchEnd(event) {
    clearTimeout(longPressTimer);
}

function handleSpeakerClick(event, ip) {
    clearTimeout(longPressTimer);
    
    const spk = globalData.speakers[ip];
    if (!spk || (spk.state !== 'ON' && spk.state !== 'STANDBY')) return;

    const isMultiModifierPressed = event.ctrlKey || event.metaKey;

    if (isMultiModifierPressed || isMultiSelectMode) {
        isMultiSelectMode = true;
        toggleSpeakerSelection(ip);
    } else {
        clearAllSpeakerSelections();
        selectSpeaker(ip);
    }
}

function toggleSpeakerSelection(ip) {
    const chk = document.getElementById(`chk-${ip}`);
    if (chk && !chk.disabled) {
        chk.checked = !chk.checked;
        chk.closest('.speaker-item').classList.toggle('selected', chk.checked);
        
        if (chk.checked) {
            if (!selectedSpeakersOrder.includes(ip)) selectedSpeakersOrder.push(ip);
        } else {
            selectedSpeakersOrder = selectedSpeakersOrder.filter(item => item !== ip);
        }
    }
    
    const selectedCount = selectedSpeakersOrder.length;
    if (selectedCount <= 1) {
        isMultiSelectMode = false;
    }
    
    updateSidebarUI();
    updatePlayerInfo();
    routePageUpdates(); // <-- FIX : Force la page centrale (now.html) à se rafraîchir
}

function clearAllSpeakerSelections() {
    document.querySelectorAll('.speaker-checkbox').forEach(chk => {
        chk.checked = false;
        const item = chk.closest('.speaker-item');
        if(item) item.classList.remove('selected');
    });
    selectedSpeakersOrder = [];
    isMultiSelectMode = false;
    updateSidebarUI();
    updatePlayerInfo(); // <-- FIX : Vide la barre de lecture en bas
    routePageUpdates(); // <-- FIX : Vide la page centrale
}

function selectSpeaker(ip) {
    const chk = document.getElementById(`chk-${ip}`);
    if (chk && !chk.disabled) {
        chk.checked = true;
        const item = chk.closest('.speaker-item');
        if(item) item.classList.add('selected');
        
        if (!selectedSpeakersOrder.includes(ip)) selectedSpeakersOrder.push(ip);
    }
    updateSidebarUI();
    updatePlayerInfo();
    routePageUpdates(); // <-- FIX : Force la page centrale (now.html) à se rafraîchir
}

function exitMultiSelectMode() {
    isMultiSelectMode = false;
    const previousMaster = selectedSpeakersOrder.length > 0 ? selectedSpeakersOrder[0] : null;
    clearAllSpeakerSelections();
    if (previousMaster) {
        selectSpeaker(previousMaster);
    }
    updateSidebarUI();
}

function updateSidebarUI() {	
    const sidebar = document.getElementById('speakers-list');
    const exitBtn = document.getElementById('exit-multi-select');
    
    if (!sidebar) return;

    if (isMultiSelectMode) {
        sidebar.classList.add('multi-select-active');
        if (exitBtn) exitBtn.style.display = 'inline-block';
    } else {
        sidebar.classList.remove('multi-select-active');
        if (exitBtn) exitBtn.style.display = 'none';
    }
    
    document.querySelectorAll('.master-badge').forEach(el => el.remove());
    
    const speakersKeys = Object.keys(globalData.speakers);
    for (const ip of speakersKeys) {
        const spk = globalData.speakers[ip];
        
        const isIntendedMaster = (isMultiSelectMode && selectedSpeakersOrder.length > 0 && selectedSpeakersOrder[0] === ip);
        const isActualMaster = (spk.is_zone_master === true);
        
        if (isIntendedMaster || isActualMaster) {
            const spkItem = document.getElementById(`chk-${ip}`);
            if (spkItem) {
                const nameDiv = spkItem.closest('.speaker-item').querySelector('.speaker-name');
                if (nameDiv && !nameDiv.querySelector('.master-badge')) {
                    nameDiv.innerHTML += ' <span class="master-badge" style="background:var(--spotify-green); color:black; font-size:10px; padding:2px 5px; border-radius:4px; margin-left:5px; font-weight:bold; vertical-align: middle;" title="Enceinte Maître">Maître</span>';
                }
            }
        }
    }
}

function mergeSpeakerData(newSpeakers) {
    for (const existingIp in globalData.speakers) {
        if (!newSpeakers[existingIp]) {
            delete globalData.speakers[existingIp];
        }
    }

    for (const ip in newSpeakers) {
        const newSpk = newSpeakers[ip];
        
        if (newSpk.is_stereo_slave) {
            if (globalData.speakers[ip]) delete globalData.speakers[ip];
            continue;
        }

        if (newSpk.source === 'RADIO_BROWSER' || newSpk.source === 'LOCAL_INTERNET_RADIO') {
            if (!newSpk.cover || newSpk.cover === 'FA_ICON' || newSpk.cover === 'SHOW_DEFAULT_IMAGE') {
                const matchName = newSpk.track || newSpk.playlist || "";
                
                if (globalData.radios && globalData.radios.length > 0 && matchName) {
                    const matchedRadio = globalData.radios.find(r => 
                        matchName.toLowerCase().includes(r.name.toLowerCase()) || 
                        r.name.toLowerCase().includes(matchName.toLowerCase())
                    );
                    if (matchedRadio && matchedRadio.logo) {
                        newSpk.cover = matchedRadio.logo;
                    } else {
                        newSpk.cover = 'FA_ICON';
                    }
                } else {
                    newSpk.cover = 'FA_ICON';
                }
            }
        }

        const oldSpk = globalData.speakers[ip] || {};

        if (newSpk.time_position !== oldSpk.time_position || newSpk.playStatus !== oldSpk.playStatus) {
            newSpk.local_time_anchor = Date.now(); 
            newSpk.local_time_base = parseInt(newSpk.time_position || 0);
        } else {
            newSpk.local_time_anchor = oldSpk.local_time_anchor || Date.now();
            newSpk.local_time_base = oldSpk.local_time_base || 0;
        }
        
        globalData.speakers[ip] = newSpk;
    }
}

const socket = io();

socket.on('bose_update', function(data) {
    mergeSpeakerData(data.speakers);
    renderSidebarDynamicElements();
    updatePlayerInfo();
    routePageUpdates();
});

document.addEventListener("DOMContentLoaded", async () => {
    await loadComponent("mobile-overlay", "components/sidebar.html", ".sidebar");
    await loadComponent(null, "components/footer.html", ".player-bar");
    await loadComponent(null, "components/remotesimple.svg", "#remote-wrapper");
    
    if (document.querySelector("#sources-wrapper")) {
        await loadComponent(null, "components/sources.svg", "#sources-wrapper");
        updateSourcesSVG(); 
    }

    highlightActiveNav();
    fetchState(); 
    setupPageListeners();
});

async function loadComponent(overlayId, fileUrl, targetSelector) {
    const target = document.querySelector(targetSelector);
    if (!target) return;
    try {
        const response = await fetch(fileUrl);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        target.innerHTML = await response.text();
    } catch (e) {
        console.error(`Erreur chargement ${fileUrl}:`, e);
    }
}

function highlightActiveNav() {
    const page = window.location.pathname.split("/").pop().replace(".html", "") || 'index';
    const activeLink = document.querySelector(`.id-nav-${page}`);
    if (activeLink) activeLink.classList.add("active");
}

function toggleMobileMenu(event) {
    if (event) event.stopPropagation();
    document.querySelector('.sidebar').classList.toggle('active');
    document.getElementById('mobile-overlay').classList.toggle('active');
}

function setupPageListeners() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchRadios();
        });
    }
}

function getSelectedIps() {
    return selectedSpeakersOrder;
}

async function fetchState() {
    if (isFetchingState) return;
    isFetchingState = true;
    try {
        const response = await fetch('/api/data');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const newData = await response.json();
        
        globalData.presets = newData.presets;
        globalData.radios = newData.radios;
        
        mergeSpeakerData(newData.speakers);
        
        renderSidebarDynamicElements();
        updatePlayerInfo();
        routePageUpdates();
    } catch (error) {
    } finally {
        isFetchingState = false;
    }
}

function routePageUpdates() {
    const page = window.location.pathname.split("/").pop();
    if (page === "index.html" || page === "") {
        const searchInput = document.getElementById('search-input');
        if (searchInput && searchInput.value.trim() === '') renderHomeGrid();
    } else if (page === "now.html") {
        if (typeof onStateUpdated === "function") {
            onStateUpdated();
        }
    }
}

function renderSidebarDynamicElements() {
    const speakersDiv = document.getElementById('speakers-list');
    if (!speakersDiv) return;

    let currentlySelected = getSelectedIps();
    const speakersKeys = Object.keys(globalData.speakers);
    let htmlSpeakers = '';
    
    if (!hasInitializedSpeakers && speakersKeys.length > 0) {
        let onSpeaker = speakersKeys.find(ip => globalData.speakers[ip].state === 'ON');
        let standbySpeaker = speakersKeys.find(ip => globalData.speakers[ip].state === 'STANDBY');
        let defaultIp = onSpeaker || standbySpeaker;
        if (defaultIp) {
            selectedSpeakersOrder = [defaultIp];
            currentlySelected = selectedSpeakersOrder;
        }
    }

    let validSelections = [];

    for (const ip of speakersKeys) {
        const data = globalData.speakers[ip];
        
        if (data.is_stereo_slave) continue;

        let statusClass = 'status-red'; 
        let isDisabled = true; 

        if (data.state === 'ON') {
            statusClass = 'status-green';
            isDisabled = false; 
        } else if (data.state === 'STANDBY') {
            statusClass = 'status-orange';
            isDisabled = false; 
        }

        let isChecked = currentlySelected.includes(ip) ? 'checked' : '';
        if (isDisabled) isChecked = '';

        if (isChecked === 'checked') validSelections.push(ip);

        let selectedClass = (isChecked === 'checked') ? 'selected' : '';
        let disabledAttr = isDisabled ? 'disabled' : '';
        let disabledStyle = isDisabled ? 'style="opacity: 0.5; cursor: not-allowed;"' : '';

        // --- GESTION DE LA BATTERIE ET DU SECTEUR ---
        let batteryHtml = '';
        if (data.battery_capable && data.battery_percent !== undefined) {
            let pct = parseInt(data.battery_percent);
            let iconClass = "fa-battery-full";
            let color = "var(--text-subdued)";
            
            if (data.running_on_battery === false) {
                iconClass = "fa-plug";
                color = "var(--spotify-green)";
            } else {
                if (pct <= 15) { iconClass = "fa-battery-empty"; color = "#FA243C"; }
                else if (pct <= 35) { iconClass = "fa-battery-quarter"; }
                else if (pct <= 65) { iconClass = "fa-battery-half"; }
                else if (pct <= 85) { iconClass = "fa-battery-three-quarters"; }
            }
            
            batteryHtml = `
            <div style="color: ${color}; font-size: 11px; display: flex; align-items: center; gap: 4px; padding-left: 5px; flex-shrink: 0;" title="${data.running_on_battery === false ? 'Sur secteur' : 'Sur batterie'}">
                <i class="fas ${iconClass}"></i> ${pct}%
            </div>`;
        }

        htmlSpeakers += `
            <div class="speaker-item ${selectedClass}" ${disabledStyle}
                 onclick="handleSpeakerClick(event, '${ip}')"
                 ontouchstart="handleSpeakerTouchStart(event, '${ip}')"
                 ontouchend="handleSpeakerTouchEnd(event)"
                 ontouchcancel="handleSpeakerTouchEnd(event)"
                 ontouchmove="handleSpeakerTouchEnd(event)">
                
                <div style="display:flex; align-items:center; gap:10px; flex: 1; min-width: 0;">
                    <div class="status-indicator ${statusClass}"></div>
                    <div class="speaker-name">${data.name || ip}</div>
                    ${batteryHtml}
                </div>
                
                <input type="checkbox" class="speaker-checkbox" id="chk-${ip}" value="${ip}" ${isChecked} ${disabledAttr} onclick="event.stopPropagation(); toggleSpeakerSelection('${ip}')">
                
                <div class="multi-check-indicator">
                    <i class="fas fa-check"></i>
                </div>
            </div>`;
    }
    
    selectedSpeakersOrder = selectedSpeakersOrder.filter(ip => validSelections.includes(ip));
    validSelections.forEach(ip => {
        if (!selectedSpeakersOrder.includes(ip)) selectedSpeakersOrder.push(ip);
    });

    speakersDiv.innerHTML = htmlSpeakers;
    
    updateSidebarUI();

    if (!hasInitializedSpeakers && speakersKeys.length > 0) {
        hasInitializedSpeakers = true;
        setTimeout(updatePlayerInfo, 100); 
    }

    const presetsDiv = document.getElementById('presets-list');
    if (presetsDiv) {
        let htmlPresets = '';
        for (let i = 1; i <= 6; i++) {
            let presetName = (globalData.presets && globalData.presets[i]) ? globalData.presets[i] : "";
            if (presetName) htmlPresets += `<div class="nav-item" onclick="playPreset('${i}')"><i class="fas fa-bookmark"></i> ${i}. ${presetName}</div>`;
        }
        presetsDiv.innerHTML = htmlPresets || '<div class="nav-item">Aucun preset</div>';
    }
    
    for (let i = 1; i <= 6; i++) {
        let presetName = (globalData.presets && globalData.presets[i]) ? globalData.presets[i] : "";
        const svgTextEl = document.getElementById(`preset-text-${i}`);
        if (svgTextEl) {
            svgTextEl.textContent = presetName.length > 14 ? presetName.substring(0, 13) + "_" : presetName;
        }
    }
}

function formatTime(seconds) {
    if (isNaN(seconds)) return "--:--";
    let m = Math.floor(seconds / 60);
    let s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function updateSourcesSVG() {
    const ips = getSelectedIps();
    if (ips.length === 0) return;
    const spk = globalData.speakers[ips[0]];
    if (!spk) return;

    const supported = spk.supported_sources || [];
    
    const sourceMap = {
        'aux': 'AUX',
        'hdmi': 'HDMI_1',
        'tv': 'TV',
        'bt': 'BLUETOOTH'
    };

    for (const [svgId, srcName] of Object.entries(sourceMap)) {
        const el = document.getElementById(svgId);
        if (el) {
            if (supported.includes(srcName)) {
                el.style.opacity = "1";
                el.style.pointerEvents = "auto";
            } else {
                el.style.opacity = "0.3";
                el.style.pointerEvents = "none";
            }
        }
    }
}

function updatePlayerInfo() {
    const ips = getSelectedIps();
    if (ips.length === 0) {
        // Nettoie l'affichage si aucune enceinte
        const trackEl = document.getElementById('player-track');
        const artistEl = document.getElementById('player-artist');
        const albumEl = document.getElementById('player-album');
        if (trackEl) trackEl.innerText = "Sélectionnez une enceinte";
        if (artistEl) artistEl.innerText = "-";
        if (albumEl) albumEl.innerText = "-";
        const coverDiv = document.getElementById('player-cover');
        if (coverDiv) {
            coverDiv.style.backgroundImage = 'none';
            coverDiv.innerHTML = `<i class="fas fa-music" style="color:#555;"></i>`;
        }
        return;
    }
    
    const spk = globalData.speakers[ips[0]];
    if (!spk) return;

    updateSourcesSVG();

    const track = spk.track || spk.playlist || "Prêt";
    const artist = spk.artist || spk.source || "Artiste inconnu";
    const album = spk.album || ""; 
    
    const trackEl = document.getElementById('player-track');
    const artistEl = document.getElementById('player-artist');
    const albumEl = document.getElementById('player-album');
    
    if (trackEl) trackEl.innerText = track;
    if (artistEl) artistEl.innerText = artist;
    if (albumEl) {
        albumEl.innerText = album;
        albumEl.style.display = album ? 'block' : 'none'; 
    }
    
    let finalCoverUrl = spk.cover;
    if (finalCoverUrl && finalCoverUrl !== 'FA_ICON' && finalCoverUrl !== 'SHOW_DEFAULT_IMAGE') {
        if (!finalCoverUrl.includes('cb=')) {
            const separator = finalCoverUrl.includes('?') ? '&' : '?';
            finalCoverUrl += `${separator}cb=${encodeURIComponent(track)}`;
        }
    }

    const coverDiv = document.getElementById('player-cover');
    if (coverDiv) {
        if (finalCoverUrl && finalCoverUrl !== 'FA_ICON' && finalCoverUrl !== 'SHOW_DEFAULT_IMAGE') {
            coverDiv.style.backgroundImage = `url('${finalCoverUrl}')`;
            coverDiv.style.backgroundSize = 'contain'; 
            coverDiv.style.backgroundPosition = 'center';
            coverDiv.style.backgroundRepeat = 'no-repeat';
            coverDiv.innerHTML = '';
        } else {
            coverDiv.style.backgroundImage = 'none';
            const iconClass = (spk.source === 'LOCAL_INTERNET_RADIO' || spk.source === 'RADIO_BROWSER') 
                              ? 'fas fa-broadcast-tower' 
                              : 'fas fa-music';
            coverDiv.innerHTML = `<i class="${iconClass}" style="color:#555;"></i>`;
        }
    }

    const playIcon = document.getElementById('play-icon');
    if (playIcon) playIcon.className = spk.playStatus === 'PLAY_STATE' ? 'fas fa-pause' : 'fas fa-play';

    const volumeSlider = document.getElementById('volume-slider'); 
    if (volumeSlider && spk.volume !== undefined) {
        if (document.activeElement !== volumeSlider) {
            volumeSlider.value = spk.volume;
        }
    }

    if ('mediaSession' in navigator) {
        let artworkArray = [];
        if (finalCoverUrl && finalCoverUrl !== 'FA_ICON' && finalCoverUrl !== 'SHOW_DEFAULT_IMAGE') {
            artworkArray = [{ src: finalCoverUrl, sizes: '512x512', type: 'image/jpeg' }];
        }
        
        navigator.mediaSession.metadata = new MediaMetadata({ 
            title: track, 
            artist: artist, 
            artwork: artworkArray 
        });
        navigator.mediaSession.setActionHandler('play', () => sendCommand('PLAY_PAUSE'));
        navigator.mediaSession.setActionHandler('pause', () => sendCommand('PLAY_PAUSE'));
        navigator.mediaSession.setActionHandler('previoustrack', () => sendCommand('PREV_TRACK'));
        navigator.mediaSession.setActionHandler('nexttrack', () => sendCommand('NEXT_TRACK'));
    }   
}

setInterval(() => {
    const ips = getSelectedIps();
    if (ips.length === 0) return;
    const spk = globalData.speakers[ips[0]];
    if (!spk) return;

    const progressFill = document.getElementById('progress-bar-fill'); 
    const timeCurrent = document.getElementById('time-current');       
    const timeTotal = document.getElementById('time-total');           

    if (spk.time_total && parseInt(spk.time_total) > 0) {
        let pos = spk.local_time_base || 0;
        if (spk.playStatus === 'PLAY_STATE') {
            pos += (Date.now() - spk.local_time_anchor) / 1000;
        }
        
        let tot = parseInt(spk.time_total);
        if (pos > tot) pos = tot;

        if (progressFill) progressFill.style.width = `${(pos / tot) * 100}%`;
        if (timeCurrent) timeCurrent.innerText = formatTime(pos);
        if (timeTotal) timeTotal.innerText = formatTime(tot);
    } else {
        if (progressFill) progressFill.style.width = `0%`;
        if (timeCurrent) timeCurrent.innerText = "--:--";
        if (timeTotal) timeTotal.innerText = "--:--";
    }
}, 250);

async function sendCommand(keyName, keyState = 'both') {
    const ips = getSelectedIps();
    if (ips.length === 0) return alert("Sélectionnez au moins une enceinte !");
    
    await fetch('/api/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ips: ips, key: keyName, state: keyState })
    });
}

// Fonction à appeler au clic sur ton nouveau bouton "Enregistrer Preset" (ex bt/aux)
function togglePresetRecordMode() {
    isPresetRecordMode = !isPresetRecordMode;
    
    // (Optionnel) Retour visuel sur le bouton pour indiquer que le mode est actif
    const btn = document.querySelector('[onclick*="togglePresetRecordMode"]');
    if (btn) {
        if (isPresetRecordMode) {
            btn.style.fill = "#FA243C"; // Rouge
            btn.style.opacity = "0.8";
        } else {
            btn.style.fill = ""; // Réinitialise
            btn.style.opacity = "0.3";
        }
    }
}

async function playPreset(presetId) {
    const ips = getSelectedIps();
    if (ips.length === 0) return alert("Sélectionnez au moins une enceinte !");

    if (isPresetRecordMode) {
        // Mode ENREGISTREMENT : Envoi de l'état 'press'
        await fetch('/api/key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips: ips, key: 'PRESET_' + presetId, state: 'press' })
        });
        
        // Désactivation du mode après l'enregistrement
        togglePresetRecordMode();
        
        // Rafraîchissement forcé pour mettre à jour les noms des presets
        setTimeout(() => fetch('/api/poll', {method: 'POST'}), 1000);
        
    } else {
        // Mode LECTURE NORMAL
        await fetch('/api/play_preset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips, preset_id: presetId })
        });
    }
}

async function createZone() {
    const ips = getSelectedIps();
    if (ips.length < 2) {
        alert("Sélectionnez au moins 2 enceintes pour créer une zone !");
        return;
    }
    try {
        const response = await fetch('/api/create_zone', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ips: ips })
        });
        const result = await response.json();
        if(result.status === 'success') {
            const masterIp = ips[0];
            const masterName = globalData.speakers[masterIp] ? globalData.speakers[masterIp].name : masterIp;
            alert(`Zone multi-room créée avec succès !\nL'enceinte maître est : ${masterName}`);
        } else {
            alert("Erreur: " + (result.message || "Impossible de grouper."));
        }
    } catch (e) {
        console.error("Erreur groupe :", e);
    }
}

async function createStereoPair() {
    const ips = getSelectedIps();
    if (ips.length !== 2) {
        alert("Pour l'option Stéréo, vous devez sélectionner EXACTEMENT 2 enceintes SoundTouch 10 !");
        return;
    }
    const groupName = prompt("Saisissez un nom pour cette Paire Stéréo (Ex: Salon) :", "Paire Stéréo");
    if (!groupName) return;
    
    try {
        const response = await fetch('/api/create_stereo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ master_ip: ips[0], slave_ip: ips[1], name: groupName })
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert("Paire stéréo créée avec succès ! L'enceinte Maître sera la Gauche (L).");
            setTimeout(fetchState, 2000);
        } else {
            alert("Erreur: " + (result.message || "Impossible de créer la paire."));
        }
    } catch (e) {
        console.error("Erreur création stéréo :", e);
    }
}

async function removeStereoPair() {
    const ips = getSelectedIps();
    if (ips.length === 0) {
        alert("Sélectionnez la paire stéréo (Maître) que vous souhaitez séparer !");
        return;
    }
    
    if (!confirm("Voulez-vous vraiment séparer cette paire stéréo ?")) return;
    
    try {
        const response = await fetch('/api/remove_stereo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip: ips[0] })
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert("Paire stéréo séparée ! (L'esclave va redémarrer et réapparaître d'ici quelques instants).");
            setTimeout(fetchState, 3000);
        }
    } catch (e) {
        console.error("Erreur suppression stéréo :", e);
    }
}

function renderHomeGrid() {
    const grid = document.getElementById('main-grid');
    if (!grid) return; 

    document.getElementById('main-title').innerText = "Vos Radios Favorites";
    if (!globalData.radios || globalData.radios.length === 0) {
        grid.innerHTML = '<p style="color:var(--text-subdued)">Vous n\'avez pas encore ajouté de radios favorites.</p>';
        return;
    }

    grid.innerHTML = globalData.radios.map(radio => {
        const cleanName = radio.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        let visualHtml = '<i class="fas fa-broadcast-tower" style="font-size: 35px; color: #888;"></i>';
        if (radio.logo && radio.logo !== 'FA_ICON') {
            visualHtml = `<img src="${radio.logo}" alt="${cleanName}" style="width: 100%; height: 100%; border-radius: 8px; object-fit: contain;">`;
        }

        return `
            <div class="card">
                <div class="card-icon" onclick="playRadio('${radio.uuid}', '${cleanName}')" title="Lancer" style="cursor: pointer; display: flex; align-items: center; justify-content: center; width: 100%; height: 70px; margin-bottom: 10px;">
                    ${visualHtml}
                </div>
                <div class="card-title" title="${radio.name}">${radio.name}</div>
                <div class="card-subtitle">Radio Web</div>
                <div class="card-actions">
                    <button class="btn-card btn-card-play" onclick="playRadio('${radio.uuid}', '${cleanName}')">▶ Lancer</button>
                    <button class="btn-card btn-card-add" style="border-color: #FA243C; color: #FA243C;" onclick="removeRadio('${radio.uuid}')" title="Supprimer"><i class="fas fa-trash"></i></button>
                </div>
            </div>`;
    }).join('');
}

async function changeVolume(volValue) {
    const ips = getSelectedIps();
    if (ips.length === 0) return;
    
    try {
        await fetch('/api/volume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips: ips, volume: parseInt(volValue) })
        });
    } catch (e) {
        console.error("Erreur lors de la modification du volume :", e);
    }
}

async function forcePollAll(event) {
    let icon = null;
    if (event && event.currentTarget) {
        icon = event.currentTarget.querySelector('i');
        if (icon) icon.classList.add('fa-spin');
    }

    try {
        await fetch('/api/poll', { method: 'POST' });
        setTimeout(fetchState, 1000); 
    } catch (e) {
        console.error("Erreur de polling forcé", e);
    } finally {
        if (icon) {
            setTimeout(() => icon.classList.remove('fa-spin'), 1500);
        }
    }
}

async function changeSource(source) {
    const ips = getSelectedIps();
    if (ips.length === 0) {
        if (typeof showNotification === 'function') showNotification("Sélectionnez une enceinte !", "error");
        return;
    }

    if (typeof showNotification === 'function') showNotification(`Basculement sur ${source}...`, "warning");
    try {
        const response = await fetch('/api/select_source', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip: ips[0], source: source })
        });
        if (response.ok) {
            if (typeof showNotification === 'function') showNotification(`✅ Source ${source} active`, "success");
            setTimeout(fetchState, 1500);
        } else {
            if (typeof showNotification === 'function') showNotification("❌ Erreur de basculement", "error");
        }
    } catch (e) {
        if (typeof showNotification === 'function') showNotification("❌ Erreur réseau", "error");
    }
}

