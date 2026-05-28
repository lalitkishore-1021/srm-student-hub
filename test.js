
        // ================= GLOBAL STATE =================
        const BACKEND_URL = 'https://srm-student-hub-1.onrender.com';
        let isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';
        let attendanceData = [];
        let timetableData = {};
        let currentBatch = 1;

        // ================= PWA ENFORCEMENT & INSTALLATION =================
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        let deferredPrompt;

        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            const installBtn = document.getElementById('installQuickActionBtn');
            if (installBtn) installBtn.style.display = 'flex';
        });

        async function installPWA() {
            if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
                alert("To install on iOS: Tap the Share icon below, then select 'Add to Home Screen'.");
                return;
            }
            if (deferredPrompt) {
                try {
                    deferredPrompt.prompt();
                    const { outcome } = await deferredPrompt.userChoice;
                    if (outcome === 'accepted') {
                        const mobileLock = document.getElementById('mobile-lock');
                        if (mobileLock) mobileLock.style.display = 'none';
                    }
                    deferredPrompt = null;
                } catch(err) {
                    console.error("Install prompt error:", err);
                }
            } else {
                alert("Please use your browser menu to 'Add to Home Screen'.");
            }
        }

        window.addEventListener('load', () => {
            if (isMobile && !isStandalone) {
                const mobileLock = document.getElementById('mobile-lock');
                if (mobileLock) mobileLock.style.display = 'flex';
            } else if (isMobile && isStandalone && !isLoggedIn) {
                setTimeout(() => openSyncModal(), 800);
            }
        });

        document.body.addEventListener('click', (e) => {
            if (e.target && e.target.innerText && typeof e.target.innerText === 'string' && e.target.innerText.includes("Continue in browser")) return;
            if (isMobile && !isStandalone && deferredPrompt) {
                installPWA();
            }
        }, { capture: true });

        window.addEventListener('appinstalled', () => {
            const installBtn = document.getElementById('installQuickActionBtn');
            if (installBtn) installBtn.style.display = 'none';
        });

        const logoTrigger = document.getElementById('logoInstallTrigger');
        if (logoTrigger) {
            logoTrigger.addEventListener('click', () => {
                if (deferredPrompt) openInstallModal();
                else alert("App is already installed or browser doesn't support installation.");
            });
        }

        function openInstallModal() { document.getElementById('installModal').style.display = 'flex'; }
        function closeInstallModal() {
            document.getElementById('installModal').style.display = 'none';
            localStorage.setItem('installDismissed', 'true');
        }

        async function installApp() {
            if (deferredPrompt) {
                closeInstallModal();
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === 'accepted') deferredPrompt = null;
            }
        }

        let currentCalDate = new Date();
        const srmPlanner = {
            "2026-07-20": { type: "Event", title: "Enrolment Day - B.Tech - II,III,IV / M.Tech" },
            "2026-07-21": { type: "Event", title: "Commencement of Classes" },
            "2026-08-01": { type: "Event", title: "Enrolment Day Starts B.Tech - I" },
            "2026-08-07": { type: "Event", title: "Enrolment Day Ends with B.Tech - I" },
            "2026-08-15": { type: "Holiday", title: "Independence Day - Holiday" },
            "2026-08-17": { type: "Event", title: "Commencement of Classes for B.Tech - I" },
            "2026-08-26": { type: "Holiday", title: "Milad - un - Nabi - Holiday" },
            "2026-09-04": { type: "Holiday", title: "Krishna Jayanthi - Holiday" },
            "2026-09-14": { type: "Holiday", title: "Vinayakar Chathurthi - Holiday" },
            "2026-10-02": { type: "Holiday", title: "Gandhi Jayanthi - Holiday" },
            "2026-10-19": { type: "Holiday", title: "Ayutha Pooja - Holiday" },
            "2026-10-20": { type: "Holiday", title: "Vijaya Dasami - Holiday" },
            "2026-11-08": { type: "Holiday", title: "Deepavali - Holiday" },
            "2026-11-18": { type: "Event", title: "Last Working Day - B.Tech" },
            "2026-12-04": { type: "Event", title: "Last Working Day - B.Tech - I" },
            "2026-12-25": { type: "Holiday", title: "Christmas - Holiday" }
        };

        // Auto-generate accurate Day Orders for 2026 Odd Semester
        const endDate = new Date(2026, 11, 4); // Dec 4th, 2026
        const holidays = ["2026-08-15", "2026-08-26", "2026-09-04", "2026-09-14", "2026-10-02", "2026-10-19", "2026-10-20", "2026-11-08", "2026-12-25"];

        let dOrder = 1;
        // Strictly deterministic integer loop completely avoiding Javascript DST / Timezone manipulation infinite loops!
        for (let i = 0; i < 150; i++) {
            let d = new Date(2026, 6, 21 + i); // Jul 21st 2026 + i days
            if (d > endDate) break;

            let curISOTime = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, '0') + "-" + String(d.getDate()).padStart(2, '0');
            let dayOfWeek = d.getDay();

            if (dayOfWeek !== 0 && dayOfWeek !== 6 && !holidays.includes(curISOTime)) {
                let existingTitle = srmPlanner[curISOTime] ? srmPlanner[curISOTime].title + ` (Day Order ${dOrder})` : `Regular Day Order ${dOrder}`;
                srmPlanner[curISOTime] = { type: "Day Order", value: dOrder, title: existingTitle };

                dOrder = dOrder === 5 ? 1 : dOrder + 1;
            }
        }

        function getDayOrder(dateStr) {
            let plan = srmPlanner[dateStr];
            if (plan && plan.type === "Day Order") return plan.value;
            if (plan && plan.value) return plan.value; // For Event type that holds Day Order
            
            // Fallback for dates outside the generated range
            let d = new Date(dateStr);
            let dayIndex = d.getDay();
            return (dayIndex >= 1 && dayIndex <= 5) ? dayIndex : 0;
        }

        function isSemesterVacation(dateStr) {
            let d = new Date(dateStr);
            let summerVacationStart = new Date("2026-05-07");
            let summerVacationEnd = new Date("2026-07-19");
            let winterVacationStart = new Date("2026-12-05");
            let winterVacationEnd = new Date("2027-01-10");
            
            return (d >= summerVacationStart && d <= summerVacationEnd) || 
                   (d >= winterVacationStart && d <= winterVacationEnd);
        }

        // ================= INITIALIZATION =================
        updateHomeState();
        loadSavedData();

        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('sw.js').catch(err => console.log('SW Failed:', err));
            });
        }

        // ================= NAVIGATION =================
        history.replaceState({ viewId: 'home-view' }, '', '#home-view');

        function switchView(viewId, pushToHistory = true) {
            document.querySelectorAll('.app-view').forEach(view => { view.classList.remove('active'); });
            document.getElementById(viewId).classList.add('active');
            window.scrollTo({ top: 0, behavior: 'smooth' });
            if (pushToHistory) history.pushState({ viewId: viewId }, '', `#${viewId}`);
        }

        function switchNav(viewId, element) {
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            element.classList.add('active');
            switchView(viewId);
        }

        window.addEventListener('popstate', (e) => {
            if (e.state && e.state.viewId) switchView(e.state.viewId, false);
            else switchView('home-view', false);
        });

        // ================= UI STATE MANAGEMENT =================
        function getCurrentNetId() {
            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const regNoRaw = document.getElementById('srm-reg')?.value || profile.regNo || '';
            return (regNoRaw.split('@')[0] || '').toLowerCase();
        }

        function updateHomeState() {
            if (isLoggedIn) {
                document.getElementById('unauth-hero').style.display = 'none';
                document.getElementById('auth-dashboard').style.display = 'block';
                document.getElementById('advisors-section').style.display = 'block';
            } else {
                document.getElementById('unauth-hero').style.display = 'block';
                document.getElementById('auth-dashboard').style.display = 'none';
                document.getElementById('advisors-section').style.display = 'none';
            }
            // Show holiday banner on home page
            checkAndShowHolidayBanner('home-holiday-banner');
            // Update holiday name if available
            let todayLocal = new Date();
            let tzoffset = todayLocal.getTimezoneOffset() * 60000;
            let dateStr = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);
            if (srmPlanner[dateStr] && srmPlanner[dateStr].type === 'Holiday') {
                let nameEl = document.getElementById('home-holiday-name');
                if (nameEl) nameEl.textContent = srmPlanner[dateStr].title + ' — No classes today!';
            }
        }

        function renderProfile(profile) {
            if (!profile || !profile.name) return;
            const nameEl = document.querySelector('.id-name');
            const regEl = document.querySelector('.id-reg');
            if (nameEl) nameEl.innerText = (profile.name || 'STUDENT').toUpperCase();
            if (regEl) regEl.innerText = (profile.regNo || '').toUpperCase();

            // Use specific IDs for detail spans
            const courseSpan = document.getElementById('id-detail-course');
            const deptSpan = document.getElementById('id-detail-dept');
            const semSpan = document.getElementById('id-detail-sem');

            let courseStr = profile.course || 'B.Tech';
            let deg = courseStr;
            // Try to extract degree program name
            if (courseStr.includes('.')) {
                deg = courseStr.split('.')[0].trim();
                if (deg.length < 2) deg = 'B.Tech';
            }

            // Department: use scraped department field if available
            let deptStr = profile.department || '';
            if (!deptStr) {
                // Fallback: try to extract from course string
                if (courseStr.includes('.')) {
                    deptStr = courseStr.split('.').slice(1).join('.').trim();
                } else {
                    deptStr = courseStr;
                }
            }

            if (courseSpan) courseSpan.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/></svg> ${deg}`;
            if (deptSpan) deptSpan.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg> ${deptStr}`;
            if (semSpan) semSpan.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg> Semester ${profile.semester || 'N/A'}`;

            // Also render advisors
            renderAdvisors(profile);
        }

        function renderAdvisors(profile) {
            if (!profile) return;

            // Faculty Advisor
            const faCard = document.getElementById('fa-card');
            if (faCard && (profile.fa_name || profile.fa_email || profile.fa_phone)) {
                faCard.style.display = 'block';
                const faNameEl = document.getElementById('fa-name');
                const faEmailEl = document.getElementById('fa-email');
                const faPhoneEl = document.getElementById('fa-phone-display');
                const faCallBtn = document.getElementById('fa-call-btn');

                if (faNameEl) faNameEl.innerText = profile.fa_name || 'Faculty Advisor';
                if (faEmailEl) faEmailEl.innerText = '@ ' + (profile.fa_email || 'N/A');
                if (faPhoneEl) faPhoneEl.innerText = '📞 ' + (profile.fa_phone || 'N/A');
                if (faCallBtn && profile.fa_phone) {
                    faCallBtn.href = 'tel:' + profile.fa_phone;
                } else if (faCallBtn) {
                    faCallBtn.style.display = 'none';
                }
            }

            // Academic Advisor
            const aaCard = document.getElementById('aa-card');
            if (aaCard && (profile.aa_name || profile.aa_email || profile.aa_phone)) {
                aaCard.style.display = 'block';
                const aaNameEl = document.getElementById('aa-name');
                const aaEmailEl = document.getElementById('aa-email');
                const aaPhoneEl = document.getElementById('aa-phone-display');
                const aaCallBtn = document.getElementById('aa-call-btn');

                if (aaNameEl) aaNameEl.innerText = profile.aa_name || 'Academic Advisor';
                if (aaEmailEl) aaEmailEl.innerText = '@ ' + (profile.aa_email || 'N/A');
                if (aaPhoneEl) aaPhoneEl.innerText = '📞 ' + (profile.aa_phone || 'N/A');
                if (aaCallBtn && profile.aa_phone) {
                    aaCallBtn.href = 'tel:' + profile.aa_phone;
                } else if (aaCallBtn) {
                    aaCallBtn.style.display = 'none';
                }
            }
        }

        function loadSavedData() {
            const savedProfile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const savedAtt = JSON.parse(localStorage.getItem('squadAttendance') || '[]');
            const savedMarks = JSON.parse(localStorage.getItem('squadMarks') || '[]');
            const savedTT = JSON.parse(localStorage.getItem('squadTimetable') || '{}');

            renderProfile(savedProfile);
            renderAttendance(savedAtt);
            renderMarks(savedMarks);
            renderTimetable(savedTT);
        }

        // ================= LIVE SYNC API CALL =================
        function toggleBatch(element, batchNum) {
            document.querySelectorAll('.batch-btn').forEach(btn => btn.classList.remove('active'));
            element.classList.add('active');
            currentBatch = batchNum;
        }

        function openSyncModal() { document.getElementById('syncModal').style.display = 'flex'; }
        function closeSyncModal() { document.getElementById('syncModal').style.display = 'none'; }
        
        function logout() {
            localStorage.clear();
            sessionStorage.clear();
            window.location.reload();
        }

        function showSyncToast() {
            let toast = document.getElementById('sync-toast');
            if (!toast) {
                toast = document.createElement('div');
                toast.id = 'sync-toast';
                toast.innerHTML = `<div class="css-loader" style="width:15px;height:15px;margin:0 10px 0 0;border-width:2px;"></div> Syncing data in background...`;
                toast.style.cssText = `position:fixed; bottom:20px; left:50%; transform:translateX(-50%); background:rgba(0,0,0,0.8); color:#fff; padding:10px 20px; border-radius:20px; font-size:0.9rem; z-index:9999; display:flex; align-items:center; border:1px solid var(--primary); font-family:'Montserrat', sans-serif;`;
                document.body.appendChild(toast);
            }
        }
        function hideSyncToast(success=true) {
            let toast = document.getElementById('sync-toast');
            if (toast) {
                toast.innerHTML = success ? `✅ Data Synced Successfully` : `❌ Background Sync Failed`;
                setTimeout(() => toast.remove(), 3000);
            }
        }

        async function startLiveSync() {
            const regNo = document.getElementById('srm-reg').value.trim();
            const pwd = document.getElementById('srm-pwd').value;
            const statusText = document.getElementById('sync-status');

            if (!regNo || !pwd) {
                alert("Please enter your NetID/Email and Password.");
                return;
            }

            let secondsPassed = 0;
            statusText.innerHTML = `🔄 Syncing with Academia... <span style="font-family: inherit; font-size: 1.1rem; color: #fff; background: rgba(255,170,0,0.2); padding: 2px 8px; border-radius: 6px;">0s</span>`;
            statusText.style.color = "var(--primary)";
            
            let timerInterval = setInterval(() => {
                secondsPassed++;
                statusText.innerHTML = `🔄 Syncing with Academia... <span style="font-family: inherit; font-size: 1.1rem; color: #fff; background: rgba(255,170,0,0.2); padding: 2px 8px; border-radius: 6px;">${secondsPassed}s</span>`;
            }, 1000);

            try {
                const res = await fetch(`${BACKEND_URL}/api/start_session`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ regNo: regNo, pwd: pwd, batch: currentBatch })
                });

                const result = await res.json();
                clearInterval(timerInterval);

                if (!result.success) {
                    statusText.innerText = `❌ ${result.error} (Failed after ${secondsPassed}s)`;
                    statusText.style.color = "var(--danger)";
                    return;
                }

                statusText.innerText = `✅ Success! Synced in ${secondsPassed} seconds.`;
                statusText.style.color = "var(--success)";

                isLoggedIn = true;
                localStorage.setItem("isLoggedIn", "true");
                
                // Store credentials for auto background sync
                localStorage.setItem("syncRegNo", regNo);
                localStorage.setItem("syncPwd", pwd);
                localStorage.setItem("syncBatch", currentBatch);

                updateHomeState();

                const attList = Array.isArray(result.data) ? result.data : [];
                const marksList = Array.isArray(result.marks) ? result.marks : [];
                const ttDict = result.timetable || {};
                const profile = result.profile || {};

                localStorage.setItem('squadProfile', JSON.stringify(profile));
                localStorage.setItem('squadAttendance', JSON.stringify(attList));
                localStorage.setItem('squadMarks', JSON.stringify(marksList));
                localStorage.setItem('squadTimetable', JSON.stringify(ttDict));

                try { renderProfile(profile); } catch (e) { console.error("Profile Render Error:", e); }
                try { renderAttendance(attList); } catch (e) { console.error("Attendance Render Error:", e); }
                try { renderMarks(marksList); } catch (e) { console.error("Marks Render Error:", e); }
                try { renderTimetable(ttDict); } catch (e) { console.error("Timetable Render Error:", e); }

                setTimeout(() => closeSyncModal(), 2000);

            } catch (e) {
                clearInterval(timerInterval);
                statusText.innerText = "❌ Could not connect to backend server.";
                statusText.style.color = "var(--danger)";
            }
        }

        async function backgroundSync() {
            const regNo = localStorage.getItem("syncRegNo");
            const pwd = localStorage.getItem("syncPwd");
            const batch = localStorage.getItem("syncBatch") || currentBatch;
            
            if (!regNo || !pwd) return; // Cannot auto sync

            showSyncToast();
            try {
                const res = await fetch(`${BACKEND_URL}/api/start_session`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ regNo, pwd, batch })
                });

                const result = await res.json();
                if (result.success) {
                    const attList = Array.isArray(result.data) ? result.data : [];
                    const marksList = Array.isArray(result.marks) ? result.marks : [];
                    const ttDict = result.timetable || {};
                    const profile = result.profile || {};

                    localStorage.setItem('squadProfile', JSON.stringify(profile));
                    localStorage.setItem('squadAttendance', JSON.stringify(attList));
                    localStorage.setItem('squadMarks', JSON.stringify(marksList));
                    localStorage.setItem('squadTimetable', JSON.stringify(ttDict));

                    try { renderProfile(profile); } catch (e) {}
                    try { renderAttendance(attList); } catch (e) {}
                    try { renderMarks(marksList); } catch (e) {}
                    try { renderTimetable(ttDict); } catch (e) {}
                    hideSyncToast(true);
                } else {
                    hideSyncToast(false);
                }
            } catch (e) {
                hideSyncToast(false);
            }
        }

        // ================= ATTENDANCE RENDERER =================
        function saveAttendance() { localStorage.setItem('squadAttendance', JSON.stringify(attendanceData)); }

        function addAttendance() {
            const nameInput = document.getElementById('att-sub-name');
            const attInput = document.getElementById('att-attended');
            const totInput = document.getElementById('att-total');
            if (!nameInput.value || !attInput.value || !totInput.value) return alert("Fill all fields");

            attendanceData.push({ id: Date.now(), courseTitle: nameInput.value, attended: parseInt(attInput.value), total: parseInt(totInput.value) });
            nameInput.value = ''; attInput.value = ''; totInput.value = '';
            saveAttendance();
            renderAttendance(attendanceData);
        }

        function deleteAttendance(id) {
            attendanceData = attendanceData.filter(item => item.id !== id);
            saveAttendance();
            renderAttendance(attendanceData);
        }

        let simulationState = {};

        function simulateAttendance(id, action) {
            if (!simulationState[id]) simulationState[id] = { bunked: 0, attended: 0 };
            if (action === 'bunk') simulationState[id].bunked++;
            else if (action === 'attend') simulationState[id].attended++;
            else if (action === 'reset') simulationState[id] = { bunked: 0, attended: 0 };
            renderAttendance(attendanceData);
        }

        function renderAttendance(attData) {
            const list = document.getElementById('attendance-list');
            if (!list) return;

            list.innerHTML = '';
            let totalAtt = 0;
            let totalClasses = 0;
            attendanceData = attData || [];

            attendanceData.forEach(sub => {
                let sim = simulationState[sub.id || sub.courseCode] || { bunked: 0, attended: 0 };
                let baseAttended = parseInt(sub.attended) || 0;
                let baseTotal = parseInt(sub.total) || 0;
                
                let attended = baseAttended + sim.attended;
                let total = baseTotal + sim.bunked + sim.attended;
                let name = sub.courseTitle || sub.name || "Unknown Subject";

                totalAtt += attended;
                totalClasses += total;

                const percentage = total === 0 ? 0 : ((attended / total) * 100).toFixed(1);
                const isGood = percentage >= 75;
                const barColor = isGood ? 'var(--success)' : 'var(--danger)';

                let statusText = isGood
                    ? `You can safely bunk <strong>${Math.floor((attended - (0.75 * total)) / 0.75)}</strong> more classes.`
                    : `Attend <strong>${Math.ceil(((0.75 * total) - attended) / 0.25)}</strong> more classes to hit 75%.`;

                let redZoneWarning = '';
                let cardStyleModifier = '';

                if (!isGood && total > 0) {
                    redZoneWarning = `<div style="color:var(--danger); font-weight:900; font-size: 0.85rem; margin-top: 15px; background: rgba(255, 68, 68, 0.1); padding: 12px; border-radius: 8px; border: 1px solid rgba(255, 68, 68, 0.3); text-align: center; letter-spacing: 1px; animation: pulse 2s infinite;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 5px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> CRITICAL ATTENDANCE: LIMIT EXCEEDED!</div>`;
                    cardStyleModifier = 'border: 1px solid rgba(255, 68, 68, 0.4); box-shadow: 0 10px 30px rgba(255, 68, 68, 0.25);';
                }

                list.innerHTML += `
                    <div class="image-card fade-in-up" style="text-align: left; padding: 25px; margin-bottom: 20px; transition: all 0.3s; ${cardStyleModifier}">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                            <h3 style="margin: 0; color: var(--text-main); font-family: 'Montserrat', sans-serif; text-transform: uppercase; font-size: 1.1rem; max-width: 70%;">${name}</h3>
                            <div style="font-size: 1.4rem; font-family: 'Montserrat', sans-serif; font-weight: bold; color: ${barColor};">${percentage}%</div>
                        </div>
                        <div class="progress-container">
                            <div class="progress-fill" style="background: ${barColor}; width: ${percentage}%; box-shadow: 0 0 12px ${barColor};"></div>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px;">
                            <div>
                                <div class="stat-text" style="color: var(--text-main); font-weight: bold;">${attended} / ${total} Attended</div>
                                <div class="stat-text" style="color:var(--text-sub); margin-top: 5px; font-size: 0.85rem;">${statusText}</div>
                            </div>
                            <!-- Bunk Meter Simulator UI -->
                            <div style="background: rgba(0,0,0,0.3); border-radius: 8px; padding: 5px; display: flex; gap: 5px; border: 1px solid var(--glass-border);">
                                <button onclick="simulateAttendance('${sub.id || sub.courseCode}', 'bunk')" style="background: rgba(255, 68, 68, 0.2); border: none; color: #ff4444; border-radius: 5px; padding: 5px 12px; font-weight: bold; cursor: pointer;">BUNK</button>
                                <button onclick="simulateAttendance('${sub.id || sub.courseCode}', 'attend')" style="background: rgba(0, 204, 102, 0.2); border: none; color: #00cc66; border-radius: 5px; padding: 5px 12px; font-weight: bold; cursor: pointer;">ATTEND</button>
                                ${(sim.bunked > 0 || sim.attended > 0) ? `<button onclick="simulateAttendance('${sub.id || sub.courseCode}', 'reset')" style="background: transparent; border: none; color: var(--text-sub); border-radius: 5px; padding: 5px; cursor: pointer;">↺</button>` : ''}
                            </div>
                        </div>
                        ${redZoneWarning}
                    </div>
                `;
            });

            const overallPerc = totalClasses > 0 ? ((totalAtt / totalClasses) * 100).toFixed(1) : "0.0";
            const overallEl = document.getElementById('overall-attendance');

            if (overallEl) {
                if (totalClasses === 0) {
                    overallEl.innerHTML = "Overall: 0%";
                    overallEl.style.color = "var(--primary)";
                } else {
                    overallEl.innerHTML = `Overall: ${overallPerc}% <br><button class="share-btn" onclick="generateShareImage('My Attendance', '${overallPerc}%', '${overallPerc >= 75 ? '#00cc66' : '#ff4444'}')"><svg viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg> Share Stats</button>`;
                    overallEl.style.color = overallPerc >= 75 ? "var(--success)" : "var(--danger)";
                }
            }

            if (isLoggedIn) {
                const attEl = document.getElementById('home-att-val');
                const courseEl = document.getElementById('home-course-val');
                const attPercBadge = document.getElementById('att-perc-badge');
                
                if (attEl) attEl.innerText = overallPerc + "%";
                if (courseEl) courseEl.innerText = attendanceData.length;
                if (attPercBadge) {
                    const op = parseFloat(overallPerc);
                    if (op >= 90) { attPercBadge.innerHTML = '🔥 TOP 5%'; attPercBadge.style.color = 'var(--primary)'; }
                    else if (op >= 80) { attPercBadge.innerHTML = '⭐ TOP 15%'; attPercBadge.style.color = '#fff'; }
                    else if (op < 75) { attPercBadge.innerHTML = '⚠️ RISK ZONE'; attPercBadge.style.color = 'var(--danger)'; }
                    else { attPercBadge.innerHTML = '📈 AVERAGE'; attPercBadge.style.color = 'var(--text-sub)'; }
                }
            }
        }

        // ================= CGPA PREDICTOR LOGIC =================
        function updateTargetLock(courseId, internalObtained, internalMax) {
            const slider = document.getElementById('target-slider-' + courseId);
            const targetVal = document.getElementById('target-val-' + courseId);
            const reqVal = document.getElementById('req-val-' + courseId);
            
            if(!slider || !targetVal || !reqVal) return;
            
            let targetTotal = parseInt(slider.value);
            targetVal.innerText = targetTotal;
            
            let finalMax = 100 - internalMax;
            let required = targetTotal - internalObtained;
            
            if (required <= 0) {
                reqVal.innerHTML = `<span style="color:var(--success)">Secured! 🎉</span>`;
            } else if (required > finalMax) {
                reqVal.innerHTML = `<span style="color:var(--danger)">Impossible (${required.toFixed(1)} / ${finalMax})</span>`;
            } else {
                reqVal.innerHTML = `<span style="color:var(--primary)">${required.toFixed(1)} / ${finalMax}</span> required in Finals`;
            }
        }

        // ================= MARKS RENDERER =================
        function renderMarks(marksData) {
            const noData = document.getElementById('marks-no-data');
            const list = document.getElementById('marks-list');

            if (!list || !noData) return;

            if (!marksData || marksData.length === 0) {
                noData.style.display = 'block';
                list.style.display = 'none';
                return;
            }

            noData.style.display = 'none';
            list.style.display = 'block';
            list.innerHTML = '';

            let grandTotalObtained = 0; let grandTotalMax = 0; let subjectsHTML = '';

            marksData.forEach(item => {
                const course = item.courseTitle || item.CourseTitle || item.name || "Subject";
                let perfString = item['Test Performance'] || item.performance || item.marks || "";

                if (!perfString && typeof item === 'object') {
                    perfString = Object.values(item).filter(v => typeof v === 'string').join(' | ');
                }

                let subjectMax = 0; let subjectObtained = 0; let testsHtml = '';
                const regex = /([A-Za-z0-9-]+)\/([0-9.]+)\s*\|\s*([0-9.]+)/g;
                let match;

                while ((match = regex.exec(perfString)) !== null) {
                    const testName = match[1]; const max = parseFloat(match[2]); const obtained = parseFloat(match[3]);
                    subjectMax += max; subjectObtained += obtained;
                    const percent = max > 0 ? Math.round((obtained / max) * 100) : 0;

                    let badgeColor = "var(--success)"; let badgeBorder = "rgba(0, 204, 102, 0.4)";
                    if (percent < 50) { badgeColor = "var(--danger)"; badgeBorder = "rgba(255, 68, 68, 0.4)"; }
                    else if (percent < 75) { badgeColor = "var(--primary)"; badgeBorder = "rgba(255, 170, 0, 0.4)"; }

                    testsHtml += `
                        <div class="test-row">
                            <div class="test-info">
                                <h4>${testName}</h4><p>${obtained} / ${max} marks</p>
                            </div>
                            <div class="test-badge" style="color: ${badgeColor}; border-color: ${badgeBorder};">${percent}%</div>
                        </div>
                    `;
                }

                if (testsHtml === '') {
                    testsHtml = `<p style="color: var(--text-sub); margin-top: 15px;">${perfString}</p>`;
                }

                grandTotalMax += subjectMax; grandTotalObtained += subjectObtained;
                let subjectPercent = subjectMax > 0 ? ((subjectObtained / subjectMax) * 100).toFixed(1) : 0;
                let courseId = course.replace(/[^a-zA-Z0-9]/g, '');

                subjectsHTML += `
                    <div class="image-card fade-in-up" style="margin-bottom: 20px; text-align: left; padding: 25px;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
                            <div>
                                <h3 style="margin: 0 0 5px 0; font-size: 1.1rem; color: var(--text-main); font-family: 'Montserrat', sans-serif; text-transform: uppercase;">${course}</h3>
                                <p style="margin: 0; font-size: 0.8rem; color: var(--primary);">THEORY</p>
                            </div>
                            ${subjectMax > 0 ? `
                            <div style="text-align: right;">
                                <h2 style="margin: 0; font-size: 1.6rem; color: var(--text-main); font-family: 'Montserrat', sans-serif;">${subjectPercent}%</h2>
                                <p style="margin: 2px 0 0 0; font-size: 0.8rem; color: var(--text-sub);">${subjectObtained.toFixed(1)} / ${subjectMax}</p>
                            </div>` : ''}
                        </div>
                        ${subjectMax > 0 ? `
                        <div class="progress-container">
                            <div class="progress-fill" style="background: var(--primary); width: ${subjectPercent}%;"></div>
                        </div>

                        <!-- Target Lock UI -->
                        <div style="margin-top: 20px; background: rgba(0,0,0,0.3); border-radius: 12px; padding: 15px; border: 1px solid var(--glass-border);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <span style="font-size: 0.9rem; color: var(--text-main); font-weight: bold;">🎯 Target Lock</span>
                                <span style="font-size: 0.9rem; color: var(--primary); font-weight: bold;"><span id="target-val-${courseId}">90</span>%</span>
                            </div>
                            <input type="range" id="target-slider-${courseId}" min="${Math.ceil(subjectObtained)}" max="100" value="90" style="width: 100%; accent-color: var(--primary); height: 8px; border-radius: 10px; outline: none; appearance: none; background: rgba(255,170,0,0.2);" oninput="updateTargetLock('${courseId}', ${subjectObtained}, ${subjectMax})">
                            <div style="text-align: center; margin-top: 12px; font-size: 0.85rem; font-weight: bold; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px;" id="req-val-${courseId}">
                                Slide to predict final exam requirements
                            </div>
                        </div>
                        
                        <div class="overview-title" style="margin: 20px 0 15px 0;"> Detailed Performance</div>
                        ` : ''}
                        <div class="test-list">
                            ${testsHtml}
                        </div>
                    </div>
                `;
            });

            const overallPercent = grandTotalMax > 0 ? ((grandTotalObtained / grandTotalMax) * 100).toFixed(1) : "0.0";
            const estCGPA = grandTotalMax > 0 ? ((grandTotalObtained / grandTotalMax) * 10).toFixed(2) : "0.00";
            let grade = "C";
            if (overallPercent >= 90) grade = "O"; else if (overallPercent >= 80) grade = "A+";
            else if (overallPercent >= 70) grade = "A"; else if (overallPercent >= 60) grade = "B+";
            else if (overallPercent >= 50) grade = "B";

            let percentileHTML = '';
            if (estCGPA >= 9.5) percentileHTML = `<div style="margin-top: 15px;"><span style="background: rgba(255,170,0,0.2); color: var(--primary); padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 900; letter-spacing: 1px; display: inline-block;">👑 TOP 2% OF BATCH</span></div>`;
            else if (estCGPA >= 9.0) percentileHTML = `<div style="margin-top: 15px;"><span style="background: rgba(255,255,255,0.1); color: #fff; padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 900; letter-spacing: 1px; display: inline-block;">🔥 TOP 10% OF BATCH</span></div>`;

            list.innerHTML = `
                <div class="dashboard-overview fade-in-up">
                    <div class="overview-title">Academic Performance</div>
                    <h1 class="overview-percent">${overallPercent}%</h1>
                    <div class="overview-stats">
                        <div class="stat-item"><h4>${estCGPA}</h4><p>Est. CGPA</p></div>
                        <div class="stat-item" style="border-left: 1px solid var(--glass-border); border-right: 1px solid var(--glass-border);">
                            <h4>${grandTotalObtained.toFixed(1)}</h4><p>Score / ${grandTotalMax}</p>
                        </div>
                        <div class="stat-item"><h4>${grade}</h4><p>Avg Grade</p></div>
                    </div>
                    ${percentileHTML}
                    <button class="share-btn" onclick="generateShareImage('My Est. CGPA', '${estCGPA}', '#ffaa00')" style="margin-top: 25px;"><svg viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg> Flex CGPA</button>
                </div>
            ` + subjectsHTML;
        }

        // ================= TIMETABLE RENDERER =================
        function checkAndShowHolidayBanner(viewId) {
            let todayLocal = new Date();
            let tzoffset = todayLocal.getTimezoneOffset() * 60000;
            let dateStr = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);
            let plan = srmPlanner[dateStr];
            let isHoliday = plan && plan.type === "Holiday";
            
            let banner = document.getElementById(viewId);
            if (banner) {
                if (isSemesterVacation(dateStr)) {
                    banner.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg><div><strong>🌴 Semester Holidays!</strong><br><small>Enjoy your vacation!</small></div>`;
                    banner.style.display = 'flex';
                } else if (isHoliday) {
                    banner.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><div><strong>🎉 Today is a Holiday!</strong><br><small>${plan.title}</small></div>`;
                    banner.style.display = 'flex';
                } else if (todayLocal.getDay() === 0 || todayLocal.getDay() === 6) {
                    banner.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><div><strong>🏖️ Weekend!</strong><br><small>No classes today.</small></div>`;
                    banner.style.display = 'flex';
                } else {
                    banner.style.display = 'none';
                }
            }
        }
        
        function showHolidaySlideUp() {
            // Deprecated - using inline banners now
        }

        function isClassActive(timeStr) {
            if (!timeStr) return false;
            try {
                let parts = timeStr.split(/[-]|to/i).map(s => s.trim());
                if (parts.length < 2) return false;
                let [startStr, endStr] = parts;
                let parseT = (t) => {
                    let [h, m] = t.trim().split(':').map(Number);
                    if (h >= 1 && h <= 7) h += 12; // PM adjustment
                    return h * 60 + m;
                };
                let startMins = parseT(startStr);
                let endMins = parseT(endStr);
                let now = new Date();
                let currentMins = now.getHours() * 60 + now.getMinutes();
                return currentMins >= startMins && currentMins <= endMins;
            } catch (e) { return false; }
        }

        function renderTimetable(ttData) {
            timetableData = ttData || {};

            const noData = document.getElementById('timetable-no-data');
            const grid = document.getElementById('timetable-grid');

            if (!noData || !grid) return;

            let hasClasses = false;
            if (typeof timetableData === 'object' && !Array.isArray(timetableData)) {
                for (let day in timetableData) {
                    if (timetableData[day] && timetableData[day].length > 0) {
                        hasClasses = true;
                        break;
                    }
                }
            }

            if (!hasClasses) {
                noData.style.display = 'block';
                grid.style.display = 'none';
                noData.querySelector('h3').innerText = "No Classes Found";
                noData.querySelector('p').innerHTML = "The scraper found zero classes. Switch between <strong style='color:var(--primary);'>Batch 1</strong> and <strong style='color:var(--primary);'>Batch 2</strong>, then click Sync again.";
                return;
            }

            noData.style.display = 'none';
            grid.style.display = 'block';

            setInitialTimetableDay();
        }
        function setInitialTimetableDay() {
            let todayLocal = new Date();
            let tzoffset = todayLocal.getTimezoneOffset() * 60000;
            let localISOTime = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);

            let dayToRender = 1;
            if (srmPlanner[localISOTime] && srmPlanner[localISOTime].type === "Day Order") {
                dayToRender = srmPlanner[localISOTime].value;
            } else {
                let dayIndex = todayLocal.getDay();
                dayToRender = (dayIndex >= 1 && dayIndex <= 5) ? dayIndex : 1;
            }

            const dayBtns = document.querySelectorAll('.tt-day-selector .day-btn');
            if (dayBtns.length > 0 && dayBtns[dayToRender - 1]) {
                renderDay(dayToRender, dayBtns[dayToRender - 1]);
            } else {
                renderDay(1, null);
            }
            // Always check holiday on timetable view load
            checkAndShowHolidayBanner('timetable-holiday-banner');
        }

        function renderDay(dayNumber, btnElement) {
            document.querySelectorAll('.tt-day-selector .day-btn').forEach(btn => btn.classList.remove('active'));
            if (btnElement) btnElement.classList.add('active');

            const grid = document.getElementById('timetable-grid');
            if (!grid) return;

            const classesForDay = timetableData[dayNumber.toString()] || [];
            grid.innerHTML = '';

            let todayLocal = new Date();
            let tzoffset = todayLocal.getTimezoneOffset() * 60000;
            let dayOrderDate = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);
            let isHoliday = srmPlanner[dayOrderDate] && srmPlanner[dayOrderDate].type === "Holiday";
            
            if (isSemesterVacation(dayOrderDate)) {
                grid.innerHTML = `<div class="image-card" style="text-align:center; padding: 20px;"><h4 style="color:var(--accent); margin:0;">🌴 Semester Holidays!</h4><p style="color:var(--text-sub); font-size:0.9rem;">Enjoy your vacation!</p></div>`;
            } else if (isHoliday) {
                grid.innerHTML = `<div class="image-card" style="text-align:center; padding: 20px;"><h4 style="color:var(--accent); margin:0;">Today Holiday</h4><p style="color:var(--text-sub); font-size:0.9rem;">${srmPlanner[dayOrderDate].title}</p></div>`;
            } else if (classesForDay.length === 0) {
                grid.innerHTML = `<div class="image-card" style="text-align:center; padding: 30px;"><h3 style="color:var(--text-sub); margin:0;">No classes scheduled for Day ${dayNumber}</h3></div>`;
            } else {
                // Remove duplicates and fallback "Period" classes if real times exist
                let normalizeStr = (s) => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
                let realSubjects = new Set(classesForDay.filter(c => !String(c.time).toLowerCase().includes('period')).map(c => normalizeStr(c.subject)));

                let deduplicated = classesForDay.filter(c => {
                    let isPeriod = String(c.time).toLowerCase().includes('period');
                    if (isPeriod && realSubjects.has(normalizeStr(c.subject))) return false;
                    return true;
                });

                let uniqueSet = new Set();
                deduplicated = deduplicated.filter(c => {
                    let str = `${c.time}|${normalizeStr(c.subject)}`;
                    if (uniqueSet.has(str)) return false;
                    uniqueSet.add(str);
                    return true;
                });

                let mergedClasses = [];
                deduplicated.forEach(cls => {
                    if (mergedClasses.length > 0) {
                        let last = mergedClasses[mergedClasses.length - 1];
                        if (normalizeStr(last.subject) === normalizeStr(cls.subject) && last.room === cls.room) {
                            let timePartsLast = String(last.time).split(/[-]|to/i);
                            let timePartsCls = String(cls.time).split(/[-]|to/i);
                            let start1 = timePartsLast[0]?.trim() || last.time;
                            let end2 = timePartsCls[1]?.trim() || String(cls.time).replace(/Period/i, '').trim();
                            last.time = `${start1} - ${end2}`;
                            return;
                        }
                    }
                    mergedClasses.push({ ...cls });
                });

                mergedClasses.forEach(cls => {
                    let currentDayOrder = getDayOrder(dayOrderDate);
                    let isActive = isClassActive(cls.time) && dayNumber == currentDayOrder;
                    let activeClass = isActive ? 'active-highlight' : '';
                    let badge = isActive ? '<span class="active-badge">HAPPENING NOW</span>' : '';

                    grid.innerHTML += `
                        <div class="tt-card fade-in-up ${activeClass}">
                            <div class="tt-time"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ${cls.time || 'N/A'} ${badge}</div>
                            <h3 class="tt-subject">${cls.subject || 'Unknown Subject'}</h3>
                            <div class="tt-room"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg> ${cls.room || 'Online/Unknown'}</div>
                        </div>
                    `;
                });
            }
        }

        // ================= CALENDAR LOGIC =================
        function renderCalendar() {
            const grid = document.getElementById('calendar-grid');
            if (!grid) return;

            const year = currentCalDate.getFullYear();
            const month = currentCalDate.getMonth();
            const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
            document.getElementById('calendar-month-year').innerText = `${monthNames[month]} ${year}`;

            grid.innerHTML = '<div class="cal-header">Sun</div><div class="cal-header">Mon</div><div class="cal-header">Tue</div><div class="cal-header">Wed</div><div class="cal-header">Thu</div><div class="cal-header">Fri</div><div class="cal-header">Sat</div>';

            const firstDay = new Date(year, month, 1).getDay();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            for (let i = 0; i < firstDay; i++) { grid.innerHTML += '<div class="cal-day empty"></div>'; }

            let todayLocal = new Date();
            let tzoffset = todayLocal.getTimezoneOffset() * 60000;
            let todayISOTime = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);

            for (let i = 1; i <= daysInMonth; i++) {
                let d = new Date(year, month, i);
                let dateStr = (new Date(d - tzoffset)).toISOString().slice(0, 10);
                let extraClass = '';
                if (dateStr === todayISOTime) extraClass += ' today';

                let plan = srmPlanner[dateStr];
                if (plan) {
                    if (plan.type === 'Holiday') extraClass += ' planner-holiday';
                    else if (plan.type === 'Day Order') extraClass += ' planner-day-order';
                }
                grid.innerHTML += `<div class="cal-day ${extraClass}" onclick="showEventDetails('${dateStr}')">${i}</div>`;
            }
            
            checkAndShowHolidayBanner('plan-holiday-banner');
        }

        function changeMonth(dir) {
            currentCalDate.setMonth(currentCalDate.getMonth() + dir);
            renderCalendar();
        }

        function checkAndShowEventPopup() {
            let todayLocal = new Date();
            let tzoffset = todayLocal.getTimezoneOffset() * 60000;
            let curISOTime = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);


            let plan = srmPlanner[curISOTime];
            let show = false;
            let t = "Notification";
            let s = "";

            let emojiList = ["🎉", "✨", "🔥"];

            if (isSemesterVacation(curISOTime)) {
                show = true;
                t = "Semester Holidays! 🌴";
                s = "Enjoy your vacation! Recharge and relax.";
                emojiList = ["🌴", "🏖️", "☀️", "🍹", "😎", "✨"];
            } else if (plan && plan.title) {
                s = plan.title;
                if (plan.title.includes("Enrolment") || plan.title.includes("Commencement")) {
                    show = true;
                    t = "Welcome Back! 🎉";
                    emojiList = ["🎉", "🚀", "🎒", "✨", "🔥"];
                } else if (plan.title.includes("Last Working Day")) {
                    show = true;
                    t = "Semester Complete! 🎓";
                    emojiList = ["🎓", "🏆", "🎊", "🥂", "💯"];
                }
            }
            
            if (show) {
                let popupTitle = document.getElementById('eventPopupTitle');
                let popupSub = document.getElementById('eventPopupSub');
                if (popupTitle) popupTitle.innerText = t;
                if (popupSub) popupSub.innerText = s;
                
                const popup = document.getElementById('eventPopup');
                if (popup) {
                    // Generate floating emoji confetti
                    document.querySelectorAll('.floating-emoji').forEach(e => e.remove());
                    for (let i = 0; i < 40; i++) {
                        let el = document.createElement('div');
                        el.className = 'floating-emoji';
                        el.innerText = emojiList[Math.floor(Math.random() * emojiList.length)];
                        el.style.position = 'absolute';
                        el.style.left = Math.random() * 100 + 'vw';
                        el.style.bottom = '-10vh';
                        el.style.fontSize = (Math.random() * 2 + 2) + 'rem';
                        el.style.opacity = Math.random() * 0.8 + 0.2;
                        el.style.animation = `floatUpConfetti ${Math.random() * 2 + 3}s ease-in forwards`;
                        el.style.animationDelay = (Math.random() * 1.5) + 's';
                        el.style.zIndex = 0;
                        popup.appendChild(el);
                    }

                    popup.style.display = 'flex';
                    setTimeout(() => { popup.style.display = 'none'; }, 5000);
                }
            }
        }

        let userReminders = JSON.parse(localStorage.getItem('userReminders') || '{}');
        let currentEditingDate = null;

        function saveCustomReminder() {
            if(!currentEditingDate) return;
            const val = document.getElementById('custom-reminder-val').value.trim();
            if(val) {
                userReminders[currentEditingDate] = val;
                document.getElementById('custom-reminder-status').innerText = "Reminder saved!";
                document.getElementById('custom-reminder-status').style.color = "#00cc66";
            } else {
                delete userReminders[currentEditingDate];
                document.getElementById('custom-reminder-status').innerText = "Reminder removed.";
                document.getElementById('custom-reminder-status').style.color = "var(--text-sub)";
            }
            localStorage.setItem('userReminders', JSON.stringify(userReminders));
            setTimeout(() => { document.getElementById('custom-reminder-status').innerText = ''; }, 3000);
        }

        function showEventDetails(dateStr) {
            currentEditingDate = dateStr;
            const card = document.getElementById('cal-event-details');
            card.style.display = 'block';
            card.style.animation = 'none';
            card.offsetHeight; /* trigger reflow */
            card.style.animation = 'fadeInUp 0.4s ease forwards';

            document.getElementById('event-date-title').innerText = new Date(dateStr).toDateString();
            
            document.getElementById('custom-reminder-val').value = userReminders[dateStr] || '';
            document.getElementById('custom-reminder-status').innerText = '';

            let plan = srmPlanner[dateStr];
            if (plan) {
                let badge = plan.type === 'Holiday' ? '<span class="special-badge" style="background: linear-gradient(135deg, #00cc66, #00994d);">Holiday</span>' : `<span class="special-badge" style="background: linear-gradient(135deg, #bf5af2, #9432c7); text-transform: uppercase;">${plan.type}</span>`;
                document.getElementById('event-desc').innerHTML = `${badge} <br><br> ${plan.title || 'No additional details.'}`;
            } else {
                document.getElementById('event-desc').innerText = "No events scheduled for this day.";
            }
        }

        // ================= GALLERY & PROJECTS =================
        const projectsDatabase = {
            'oopsBanner': { title: 'OOPS Banner App', subProjects: [{ id: 'ucsFolder', title: "UC's" }, { id: 'week1Problem', title: 'Week 1 & 2 Problems' }, { id: 'week34Problem', title: 'Week 3 & 4 Problems' }, { id: 'helloAppFolder', title: "HelloApp UC's" }, { id: 'week78ProblemI', title: 'week 7 and 8 problems i' }] },
            'ucsFolder': { title: "OOPS Banner App UC's", parent: 'oopsBanner', images: [{ src: 'images/oops-banner/uc1.png', label: '1' }, { src: 'images/oops-banner/uc2.png', label: '2' }, { src: 'images/oops-banner/uc3.png', label: '3' }, { src: 'images/oops-banner/uc4.png', label: '4' }, { src: 'images/oops-banner/uc5.png', label: '5' }, { src: 'images/oops-banner/uc6.png', label: '6' }, { src: 'images/oops-banner/uc7.png', label: '7' }, { src: 'images/oops-banner/uc8.png', label: '8' }, { src: 'images/oops-banner/uc9.png', label: '9' }, { src: 'images/oops-banner/uc10.png', label: '10' }, { src: 'images/oops-banner/end.png', label: 'end' }] },
            'week1Problem': { title: 'Week 1 and 2 Problems', parent: 'oopsBanner', images: [{ src: 'images/oops-banner/Basic-step1.png', label: 'Basic-Step' }, { src: 'images/oops-banner/Basic-step2.png', label: 'Basic-Step' }, { src: 'images/oops-banner/level1.png', label: 'Part 1' }, { src: 'images/oops-banner/level12.png', label: 'Part 2' }, { src: 'images/oops-banner/level13.png', label: 'Part 3' }, { src: 'images/oops-banner/bash.png', label: 'Bash' }, { src: 'images/oops-banner/level21.png', label: 'Part 4' }, { src: 'images/oops-banner/level22.png', label: 'Part 5' }, { src: 'images/oops-banner/level3.png', label: 'Part 6' }] },
            'week34Problem': { title: 'Week 3 and 4 Problems', parent: 'oopsBanner', images: [{ src: 'images/oops-banner/w31.png', label: 'Step1' }, { src: 'images/oops-banner/w32.png', label: 'Step2' }, { src: 'images/oops-banner/w33.png', label: 'Step3' }, { src: 'images/oops-banner/w34.png', label: 'Step4' }, { src: 'images/oops-banner/w35.png', label: 'Step5' }, { src: 'images/oops-banner/w36.png', label: 'Step6' }, { src: 'images/oops-banner/end.png', label: 'end' }] },
            'helloAppFolder': { title: "HelloApp UC's", parent: 'oopsBanner', video: 'https://www.youtube.com/embed/k8eX_rkQxPk', images: [{ src: 'images/oops-banner/ha1.png', label: 'uc 1 Step 1' }, { src: 'images/oops-banner/ha2.png', label: 'Step 2' }, { src: 'images/oops-banner/ha3.png', label: 'Step 3' }, { src: 'images/oops-banner/ha4.png', label: 'Step 4' }, { src: 'images/oops-banner/ha5.png', label: 'uc 2 Step 5' }, { src: 'images/oops-banner/ha6.png', label: 'Step 6' }, { src: 'images/oops-banner/ha7.png', label: 'uc 3 Step 7' }, { src: 'images/oops-banner/ha8.png', label: 'Step 8' }, { src: 'images/oops-banner/ha9.png', label: 'Step 8' }, { src: 'images/oops-banner/ha10.png', label: 'Step 9' }, { src: 'images/oops-banner/ha11.png', label: 'Step 10' }, { src: 'images/oops-banner/ha12.png', label: 'Step 11' }, { src: 'images/oops-banner/ha13.png', label: 'Step 12' }, { src: 'images/oops-banner/ha14.png', label: 'Step 13' }, { src: 'images/oops-banner/end.png', label: 'end' }] },
            'week78ProblemI': { title: 'week 7 and 8 problems ', parent: 'oopsBanner', images: [{ src: 'images/oops-banner/aa1.png', label: 'Step1' }, { src: 'images/oops-banner/aa2.png', label: 'Step1' }, { src: 'images/oops-banner/aa3.png', label: 'Step1' }, { src: 'images/oops-banner/end.png', label: 'end' }] }
        };

        function openProject(projectId) {
            switchView('gallery-view');
            const projectData = projectsDatabase[projectId];
            document.getElementById('dynamic-project-title').innerText = projectData.title;
            const galleryElement = document.getElementById('dynamic-gallery');
            galleryElement.innerHTML = '';

            if (projectData.subProjects) {
                projectData.subProjects.forEach(sub => {
                    galleryElement.innerHTML += `
                        <div class="image-card project-card fade-in-up" onclick="openProject('${sub.id}')">
                            <div class="project-cover">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="project-icon"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                            </div>
                            <div class="caption">${sub.title}</div>
                        </div>
                    `;
                });
            }

            if (projectData.video) {
                galleryElement.innerHTML += `
                    <div class="image-card fade-in-up" style="grid-column: 1 / -1; max-width: 800px; margin: 0 auto; width: 100%;">
                        <div class="video-container"><iframe src="${projectData.video}" allowfullscreen></iframe></div>
                        <div class="caption" style="color: var(--primary);">Video Tutorial</div>
                    </div>
                `;
            }

            if (projectData.images) {
                projectData.images.forEach(imgData => {
                    galleryElement.innerHTML += `
                        <div class="image-card fade-in-up">
                            <img src="${imgData.src}" alt="${imgData.label}" class="gallery-item" onclick="openLightbox(this.src)">
                            <div class="caption">${imgData.label}</div>
                        </div>
                    `;
                });
            }

            const backBtn = document.querySelector('#gallery-view .back-btn');
            if (projectData.parent) {
                backBtn.onclick = () => openProject(projectData.parent);
                backBtn.innerHTML = '&#8592; Back to ' + projectsDatabase[projectData.parent].title;
            } else {
                backBtn.onclick = () => switchNav('home-view', document.querySelector('.nav-item'));
                backBtn.innerHTML = '&#8592; Back to Home';
            }
        }

        // ================= CGPA CALCULATOR =================
        function addCgpaRow() {
            document.getElementById('cgpa-rows').insertAdjacentHTML('beforeend', `
                <div class="form-row fade-in-up">
                    <input type="text" placeholder="Subject Name (Optional)">
                    <select class="cgpa-grade">
                        <option value="">Grade</option>
                        <option value="10">O</option><option value="9">A+</option><option value="8">A</option>
                        <option value="7">B+</option><option value="6">B</option><option value="5">C</option>
                    </select>
                    <input type="number" class="cgpa-credit" placeholder="Credits" min="1" max="10">
                    <button class="danger-btn" onclick="this.parentElement.remove()">X</button>
                </div>
            `);
        }
        function calculateCGPA() {
            const grades = document.querySelectorAll('.cgpa-grade'); const credits = document.querySelectorAll('.cgpa-credit');
            let totalPoints = 0; let totalCredits = 0;
            for (let i = 0; i < grades.length; i++) {
                let gradeVal = parseFloat(grades[i].value); let creditVal = parseFloat(credits[i].value);
                if (!isNaN(gradeVal) && !isNaN(creditVal)) { totalPoints += (gradeVal * creditVal); totalCredits += creditVal; }
            }
            const resultBox = document.getElementById('cgpa-result');
            resultBox.style.display = 'block';
            if (totalCredits === 0) resultBox.innerText = "Please enter valid grades and credits!";
            else resultBox.innerText = `Your CGPA: ${(totalPoints / totalCredits).toFixed(2)}`;
        }

        // ================= MESS MENU =================
        const mealIcons = {
            'Breakfast': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M17 8h1a4 4 0 1 1 0 8h-1"/><path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z"/><line x1="6" y1="2" x2="6" y2="4"/><line x1="10" y1="2" x2="10" y2="4"/><line x1="14" y1="2" x2="14" y2="4"/></svg>',
            'Lunch': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>',
            'Snacks': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M2 21c1.2-1.5 3-2 4-2 1.9 0 2.8.5 4 2 1.2-1.5 3-2 4-2 1.9 0 2.8.5 4 2"/><path d="M3 7a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v4a7 7 0 0 1-7 7h-4a7 7 0 0 1-7-7z"/></svg>',
            'Dinner': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>'
        };

        const messMenuData = {
            'Monday': { Breakfast: 'Bread, Butter, Jam, Ghee Pongal, Sambar, Coconut Chutney, Vadai, Tea/Coffee/Milk / Boiled Egg (1 Piece), Poori, Potato Masala, Herbal Kanji', Lunch: 'Payasam, Ghee Chappathi, Green Peas Masala, Variety Rice, Steamed Rice, Sambar, Dal Lasooni, Tomato Rasam, Gobi-65 OR Bitter Guard-65, Raw Banana Chops, Millet Kanji, Special Fryums, Butter Milk, Pickle', Snacks: 'Pav Bajji, Tea/Coffee', Dinner: 'Malabar Paratha, Mix Veg Kuruma, Millet Dosa, Idly Podi, Oil, Special Chutney, Steamed Rice, Chilli Sambar, Jeera Dal, Rasam, Aloo Capsicum, Pickle, Fryums, Veg-Salad, Banana, Millet Kanji, *** Dry Fish Gravy ***' },
            'Tuesday': { Breakfast: 'Bread, Butter, Jam, Idly, Veg Kosthu, Spl Chutney, Poha, Mint Chutney, Tea/Coffee/Milk, Herbal Kanji, Masala Omlet (1 Piece)', Lunch: 'Millet Sweet, Luchi, Kashmiri Dum Aloo, Jeera Pulao, Steamed Rice, Masala Sambar, Bagara Dal, Mix Veg Usili, Pepper Rasam, Lauki Subji, Pickle, Millet Kanji, Butter Milk, Fryums', Snacks: 'Boiled Peanut / Black Channa Sundal, Tea/Coffee', Dinner: 'Chappathi, Aloo Chenna Khurma, Fried Rice / Noodles / Pastha, Manchurian Gravy / Crispy Vegetable, Steamed Rice, Rasam, Dal Fry, Millet Kanji, Pickle, Fryums, Veg-Salad, Milk, Spl Fruits, *** Chicken Gravy ***' },
            'Wednesday': { Breakfast: 'Bread, Butter, Jam, Millet Dosa, Idly Podi, Oil, Arachivitta Sambar, Chutney, Butter Chappathi, Aloo Rajma Masala, Herbal Kanji, Tea/Coffee/Milk', Lunch: 'Chappathi, Soya Kasa, Suitani Pulao, Steamed Rice, Mysore Dal Fry, Kadi Pakoda, Garlic Rasam, Aloo Palak (or) Aloo Paruval, Yam Mochai Roast, Pickle, Fryums, Millet Kanji, Butter Milk', Snacks: 'Veg Puff / Sweet Bun, Tea/Coffee', Dinner: 'Chappathi, Steamed Rice, Dal Tadka, Chicken Masala / Chilli Chicken (Non-Veg) / Paneer Butter Masala, Rasam, Pickle, Millet Kanji, Fryums, Veg Salad, Milk, Banana, *** Chicken Gravy ***' },
            'Thursday': { Breakfast: 'Bread, Butter, Jam, Chappathi, Dal Masala, Veg Semiya Kichadi, Coconut Chutney, Boiled Egg (1 Piece), Banana, Herbal Kanji, Tea/Coffee/Milk', Lunch: 'Poori, Aloo Mutar Ghughni, Corn Pulao, Punjabi Dal Tadka, Kadai Vegetable, Steamed Rice, Drumstick Brinjal Sambar, Pineapple Rasam, Beetroot Poriyal, Pickle, Fryums, Millet Kanji, Butter Milk', Snacks: 'Pani Poori (or) Mixture, Tea/Coffee', Dinner: 'Ghee Pulao / Kaji Pulao (Basmati Rice), Chappathi, Rajma Paneer, Steamed Rice, Chole Dal Fry, Rasam, Aloo Peanut Masala, Fryums, Pickle, Veg Salad, Milk, Ice Cream, *** Chicken Gravy ***' },
            'Friday': { Breakfast: 'Bread, Butter, Jam, Onion Podi Uthappam, Idly Podi, Oil, Chilli Sambar, Kara Chutney, Ghee Chappathi, Muttar Masala, Tea/Coffee/Milk, Boiled Egg (1 Piece), Herbal Kanji', Lunch: 'Spl Dry Jamun / Bread Halwa, Veg Briyani, Mix Raitha, Bisebelabath, Curd Rice, Steamed Rice, Tomato Rasam, Aloo Gobi Adaraki, Moongdal Tadka, Millet Kanji, Pickle, Potato Chips', Snacks: 'Bonda / Sambar Vada, Chutney, Tea/Coffee', Dinner: 'Chole Bhatura, Steamed Rice, Tomato Dal, Veg Upma, Coconut Chutney, Rasam, Cabbage Thoran, Pickle, Fryums, Veg Soup, Banana, Veg Salad, Milk, *** Mutton Gravy ***' },
            'Saturday': { Breakfast: 'Bread, Butter, Jam, Chappathi, Aloo Meal Maker Kasa, Idiyappam (Lemon or Masala or Coconut Milk), Coconut Chutney, Tea/Coffee/Milk, Boiled Egg (1 Piece), Herbal Kanji', Lunch: 'Butter Roti, Aloo Double Beans Masala, Veg Pulao, Steamed Rice, Dal Makhni, Bhindi Do Pyasa, Parupu Urundai Kuzhambu, Kootu, Jeera Rasam, Pickle, Special Fryums, Millet Kanji, Butter Milk', Snacks: 'Cake (or) Browni, Tea/Coffee', Dinner: 'Sweet, Panjabi Paratha, Rajma Makan Wala, French Fry, Steamed Rice, Mysore Dal Fry, Veg Idly, Idly Podi, Oil, Chutney, Tiffen Sambar, Rasam, Pickle, Fryums, Veg Salad, Milk, Millet Kanji, Special Fruit, *** Fish Gravy ***' },
            'Sunday': { Breakfast: 'Bread, Butter, Jam, Chole Poori, Veg Upma, Coconut Chutney, Tea/Coffee/Milk, Herbal Kanji', Lunch: 'Chappathi, Chicken (Pepper / Kadai), Paneer Butter Masala (or) Kadai Paneer, Dal Dhadka, Mint Pulao, Steamed Rice, Garlic Rasam, Poriyal, Pickle, Fryums, Butter Milk, Millet Kanji, *** Chicken Gravy ***', Snacks: 'Corn / Bajji, Chutney (OR) Juice, Tea/Coffee', Dinner: 'Variety Stuffing Paratha, Curd, Steamed Rice, Hara Moong Dal Tadka, Kathamba Sambar, Poriyal, Rasam, Pickle, Fryums, Veg Salad, Milk, Ice Cream, Millet Kanji, *** Chicken Gravy ***' }
        };

        function openTodayMessMenu() {
            const daysOfWeek = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
            const todayIndex = new Date().getDay();
            const currentDay = daysOfWeek[todayIndex];

            switchView('mess-view');
            renderMessMenu(currentDay);
        }

        function renderMessMenu(selectedDay) {
            const tabContainer = document.getElementById('mess-tabs'); const contentContainer = document.getElementById('mess-content');
            tabContainer.innerHTML = ''; contentContainer.innerHTML = '';

            const currentHr = new Date().getHours();
            let activeMeal = '';
            if (currentHr < 11) activeMeal = 'Breakfast'; // 0 to 10:59
            else if (currentHr < 15) activeMeal = 'Lunch'; // 11:00 to 14:59
            else if (currentHr < 18) activeMeal = 'Snacks'; // 15:00 to 17:59
            else activeMeal = 'Dinner'; // 18:00 onwards

            const isToday = new Date().getDay() === ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].indexOf(selectedDay);

            Object.keys(messMenuData).forEach(day => {
                const btn = document.createElement('button');
                btn.className = `tab-btn ${day === selectedDay ? 'active' : ''}`;
                btn.innerText = day;
                btn.onclick = () => renderMessMenu(day);
                tabContainer.appendChild(btn);
                if (day === selectedDay) setTimeout(() => btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' }), 150);
            });

            Object.entries(messMenuData[selectedDay]).forEach(([time, items]) => {
                let formattedText = items.split(', ').join(' <span style="color: var(--primary); font-weight: bold; padding: 0 5px;">&bull;</span> ');
                formattedText = formattedText.replace(/\*\*\*(.*?)\*\*\*/g, '<br><span class="special-badge">🔥 $1 🔥</span>');

                let highlightClass = (isToday && time === activeMeal) ? 'active-highlight' : '';
                let badge = (isToday && time === activeMeal) ? '<span class="active-badge">NOW SERVING</span>' : '';

                contentContainer.innerHTML += `
                    <div class="meal-card fade-in-up ${highlightClass}" style="display: flex; gap: 20px; align-items: flex-start;">
                        <div class="meal-icon-box">${mealIcons[time]}</div>
                        <div class="meal-content"><h3>${time} ${badge}</h3><p>${formattedText}</p></div>
                    </div>
                `;
            });
        }

        // ================= UTILITIES & HELPERS =================
        // ================= PULL TO REFRESH =================
        let pStart = { y: 0 };
        let pCurrent = { y: 0 };
        let ptrEl = null;

        window.addEventListener('load', () => {
            ptrEl = document.createElement('div');
            ptrEl.className = 'ptr-container';
            ptrEl.innerHTML = '<div class="ptr-spinner">↓</div>';
            document.body.appendChild(ptrEl);

            document.addEventListener('touchstart', e => { 
                if(window.scrollY === 0) pStart.y = e.touches[0].clientY; 
            }, {passive: true});

            document.addEventListener('touchmove', e => {
                if(window.scrollY === 0 && pStart.y > 0) {
                    pCurrent.y = e.touches[0].clientY;
                    let diff = pCurrent.y - pStart.y;
                    
                    if (diff > 50 && diff < 150) {
                        ptrEl.style.transform = `translateY(${diff * 0.5}px)`;
                        ptrEl.querySelector('.ptr-spinner').innerHTML = '↓';
                        ptrEl.querySelector('.ptr-spinner').style.transform = `rotate(${diff}deg)`;
                    } else if (diff >= 150) {
                        ptrEl.style.transform = `translateY(75px)`;
                        ptrEl.querySelector('.ptr-spinner').innerHTML = '↻';
                    }
                }
            }, {passive: true});

            document.addEventListener('touchend', e => {
                let diff = pCurrent.y - pStart.y;
                if (window.scrollY === 0 && diff >= 150 && pStart.y > 0) {
                    ptrEl.classList.add('active');
                    ptrEl.querySelector('.ptr-spinner').classList.add('spinning');
                    ptrEl.querySelector('.ptr-spinner').innerHTML = '↻';
                    
                    // Trigger sync modal
                    openSyncModal();
                    
                    setTimeout(() => {
                        ptrEl.style.transform = 'translateY(0)';
                        ptrEl.classList.remove('active');
                        ptrEl.querySelector('.ptr-spinner').classList.remove('spinning');
                    }, 1000);
                } else if (ptrEl && !ptrEl.classList.contains('active')) {
                    ptrEl.style.transform = 'translateY(0)';
                }
                pCurrent.y = 0; pStart.y = 0;
            });
        });

        function updateLiveHighlighting() {
            if (document.getElementById('timetable-view').classList.contains('active')) {
                const dayBtns = document.querySelectorAll('.tt-day-selector .day-btn');
                let activeBtn = null; let activeDay = 1;
                dayBtns.forEach((btn, idx) => { if (btn.classList.contains('active')) { activeBtn = btn; activeDay = idx + 1; } });

                let todayLocal = new Date();
                let tzoffset = todayLocal.getTimezoneOffset() * 60000;
                let localISOTime = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);

                let expectedDayOrder = getDayOrder(localISOTime) || 1;

                // If currently viewing "Today's" Day Order, refresh to update the "Happening Now" highlights
                if (activeDay == expectedDayOrder) {
                    renderDay(activeDay, activeBtn);
                }
            }
            if (document.getElementById('mess-view').classList.contains('active')) {
                const messBtns = document.querySelectorAll('#mess-tabs .tab-btn');
                messBtns.forEach(btn => { if (btn.classList.contains('active')) renderMessMenu(btn.innerText); });
            }
        }
        setInterval(updateLiveHighlighting, 60000);

        function toggleTheme() {
            document.body.classList.toggle('light-mode');
            document.getElementById('themeToggle').innerText = document.body.classList.contains('light-mode') ? '🌙' : '☀️';
        }

        function initApp() {
            const mainContent = document.getElementById('main-content');
            const navBtn = document.getElementById('navButtons');
            if (mainContent) mainContent.classList.add('content-visible');
            if (navBtn) navBtn.style.opacity = '1';

            let storedProfile = localStorage.getItem('squadProfile');
            if (storedProfile) {
                isLoggedIn = true;
                const profile = JSON.parse(storedProfile);
                document.getElementById('welcomeName').innerText = "Hi, " + (profile.name ? profile.name.split(' ')[0] : 'User') + " 👋";
                
                const logoutBtn = document.getElementById('logoutBtn');
                if (logoutBtn) logoutBtn.style.display = 'flex';

                loadSavedData();
                showTab('dashboard');
                
                // Start background sync
                backgroundSync();

                // Show event popup
                setTimeout(() => { checkAndShowEventPopup(); }, 1000);
            }
            if (typeof checkAndScheduleNotifications === 'function') {
                checkAndScheduleNotifications();
            }
        }
        
        // Execute initialization
        initApp();

        function requestNotificationPermission() {
            if (!("Notification" in window)) alert("This browser does not support desktop notification");
            else if (Notification.permission === "granted") { 
                alert("Notifications are already enabled!"); 
                checkAndScheduleNotifications(true); 
                registerPeriodicSync();
            }
            else if (Notification.permission !== "denied") {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") {
                        alert("Notifications enabled! You will now receive daily mess updates.");
                        checkAndScheduleNotifications(true);
                        registerPeriodicSync();
                    }
                });
            }
        }

        async function registerPeriodicSync() {
            if ('serviceWorker' in navigator) {
                const registration = await navigator.serviceWorker.ready;
                if ('periodicSync' in registration) {
                    try {
                        const status = await navigator.permissions.query({ name: 'periodic-background-sync' });
                        if (status.state === 'granted') {
                            await registration.periodicSync.register('check-notifications', {
                                minInterval: 12 * 60 * 60 * 1000 // Best effort 12 hours interval for true background wakeup
                            });
                            console.log('Periodic background sync registered!');
                        }
                    } catch (e) { console.error('Periodic Sync Error:', e); }
                }
            }
        }

        function openLightbox(src) { document.getElementById("lightbox").style.display = "flex"; document.getElementById("lightbox-img").src = src; }
        function closeLightbox() { document.getElementById("lightbox").style.display = "none"; }

        function triggerLocalNotification(title, body) {
            if (Notification.permission === 'granted' && navigator.serviceWorker) {
                navigator.serviceWorker.ready.then(reg => reg.active.postMessage({ type: 'SHOW_NOTIFICATION', title, body }));
            }
        }

        function checkAndScheduleNotifications(force = false) {
            if (Notification.permission !== 'granted') return;
            const now = new Date(), hours = now.getHours(), minutes = now.getMinutes(), timeFloat = hours + (minutes / 60);
            const todaysMenu = messMenuData[['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][now.getDay()]];
            let notifiedEvents = JSON.parse(localStorage.getItem('notifiedEvents') || '{}');

            if (localStorage.getItem('lastNotifiedDate') !== now.toDateString()) {
                notifiedEvents = { breakfast: false, lunch: false, snacks: false, dinner: false, sleep: false, custom: false };
                localStorage.setItem('lastNotifiedDate', now.toDateString());
            }

            // Check custom reminders
            let tzoffset = now.getTimezoneOffset() * 60000;
            let todayISOTime = (new Date(now - tzoffset)).toISOString().slice(0, 10);
            let reminders = JSON.parse(localStorage.getItem('userReminders') || '{}');
            if (reminders[todayISOTime] && !notifiedEvents.custom) {
                triggerLocalNotification("Calendar Reminder 📅", reminders[todayISOTime]);
                notifiedEvents.custom = true;
            }

            if (timeFloat >= 6.5 && timeFloat < 10 && !notifiedEvents.breakfast) { triggerLocalNotification("Good Morning! ☀️ Breakfast:", todaysMenu.Breakfast); notifiedEvents.breakfast = true; }
            if (timeFloat >= 11 && timeFloat < 14 && !notifiedEvents.lunch) { triggerLocalNotification("Lunch Time Approaching! 🍛", todaysMenu.Lunch); notifiedEvents.lunch = true; }
            if (timeFloat >= 15 && timeFloat < 18 && !notifiedEvents.snacks) { triggerLocalNotification("Snack Time! 🥨", todaysMenu.Snacks); notifiedEvents.snacks = true; }
            if (timeFloat >= 18.5 && timeFloat < 21 && !notifiedEvents.dinner) { triggerLocalNotification("Dinner is served! 🍽️", todaysMenu.Dinner); notifiedEvents.dinner = true; }
            if (timeFloat >= 22.5 && !notifiedEvents.sleep) { triggerLocalNotification("Time to Sleep! 🌙", "Put the phone away and get some rest for classes tomorrow. 💤"); notifiedEvents.sleep = true; }

            localStorage.setItem('notifiedEvents', JSON.stringify(notifiedEvents));
        }

        // ================= SHARING =================
        async function generateShareImage(title, value, color) {
            // Setup Holographic Modal UI
            document.getElementById('holoShareModal').style.display = 'flex';
            document.getElementById('holo-title').innerText = title;
            document.getElementById('holo-value').innerText = value;
            document.getElementById('holo-value').style.background = `linear-gradient(to bottom, #fff, ${color})`;
            document.getElementById('holo-value').style.webkitBackgroundClip = 'text';
            document.getElementById('holo-value').style.webkitTextFillColor = 'transparent';

            const card = document.getElementById('holo-card');
            const glare = document.getElementById('holo-glare');
            const container = document.getElementById('holo-card-container');

            // 3D Tilt Effect logic
            container.addEventListener('mousemove', (e) => {
                const rect = container.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                
                const rotateX = ((y - centerY) / centerY) * -20;
                const rotateY = ((x - centerX) / centerX) * 20;

                card.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
                
                // Move glare
                glare.style.opacity = '1';
                glare.style.transform = `translate(${x * 0.5}px, ${y * 0.5}px) rotate(45deg)`;
            });

            container.addEventListener('mouseleave', () => {
                card.style.transform = `rotateX(0deg) rotateY(0deg)`;
                card.style.transition = 'transform 0.5s ease';
                glare.style.opacity = '0';
                setTimeout(() => card.style.transition = 'transform 0.1s', 500);
            });
            
            // Setup Device Orientation for Mobile Tilt
            if (window.DeviceOrientationEvent) {
                window.addEventListener("deviceorientation", function(e) {
                    if (document.getElementById('holoShareModal').style.display === 'flex') {
                        let tiltLR = e.gamma;
                        let tiltFB = e.beta;
                        if(tiltLR > 30) tiltLR = 30; if(tiltLR < -30) tiltLR = -30;
                        if(tiltFB > 60) tiltFB = 60; if(tiltFB < 0) tiltFB = 0;
                        
                        const rotateY = (tiltLR / 30) * 20;
                        const rotateX = ((tiltFB - 30) / 30) * -20;
                        card.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
                    }
                }, true);
            }

            // Hook up download button
            const dlBtn = document.getElementById('downloadHoloBtn');
            dlBtn.onclick = () => downloadShareImage(title, value, color, dlBtn);
        }

        async function downloadShareImage(title, value, color, btn) {
            const originalHTML = btn.innerHTML;
            btn.innerHTML = `<div class="css-loader" style="width: 20px; height: 20px; margin: 0;"></div>`;
            
            const template = document.getElementById('share-template');
            
            const originalTop = template.style.top;
            const originalLeft = template.style.left;
            const originalOpacity = template.style.opacity;
            template.style.top = '0px';
            template.style.left = '0px';
            template.style.opacity = '1';

            document.getElementById('st-title').innerText = title;
            document.getElementById('st-value').innerText = value;
            document.getElementById('st-value').style.background = `linear-gradient(to bottom, #fff, ${color})`;
            document.getElementById('st-value').style.webkitBackgroundClip = 'text';

            try {
                const canvas = await html2canvas(template, {
                    scale: 1, backgroundColor: '#050505',
                    width: 1080, height: 1920, useCORS: true
                });
                
                canvas.toBlob(async (blob) => {
                    const file = new File([blob], 'srm-hub-stats.png', { type: 'image/png' });
                    if (navigator.canShare && navigator.canShare({ files: [file] })) {
                        await navigator.share({
                            title: 'My SRM Stats',
                            text: 'Flexing my stats! 🔥 Hosted on SRM Student Hub.',
                            files: [file]
                        });
                    } else {
                        const link = document.createElement('a');
                        link.download = 'srm-hub-stats.png';
                        link.href = canvas.toDataURL();
                        link.click();
                    }
                    btn.innerHTML = originalHTML;
                }, 'image/png');
            } catch (err) {
                console.error("Error generating image", err);
                alert("Failed to generate share image.");
                btn.innerHTML = originalHTML;
            } finally {
                template.style.top = originalTop || '';
                template.style.left = originalLeft || '';
                template.style.opacity = originalOpacity || '';
            }
        }

        // ============ LEADERBOARD ============
        let currentLeaderboardType = 'attendance';

        function switchLeaderboard(type, el) {
            document.querySelectorAll('#lb-tabs .tab-btn').forEach(b => b.classList.remove('active'));
            el.classList.add('active');
            loadLeaderboard(type);
        }

        async function loadLeaderboard(type) {
            currentLeaderboardType = type;
            const list = document.getElementById('lb-list');
            if (!list) return;
            list.innerHTML = '<div class="css-loader" style="margin: 60px auto;"></div>';
            try {
                const res = await fetch(`${BACKEND_URL}/api/leaderboard/${type}`);
                const data = await res.json();
                if (!data || data.length === 0) {
                    list.innerHTML = '<div style="text-align:center; padding: 60px 20px; color: var(--text-sub); font-size: 1.1rem;">No data yet. Be the first to sync! 🚀</div>';
                    return;
                }

                // Get current user details from localStorage to highlight them
                const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
                const myRegRaw = profile.regNo || '';
                const myNetId = myRegRaw.split('@')[0].toUpperCase();

                const rankEmojis = ['🥇', '🥈', '🥉'];
                list.innerHTML = data.map((s, i) => {
                    const val = type === 'attendance' ? `${s.overall_attendance}%` : `CGPA ${s.est_cgpa}`;
                    const color = type === 'attendance'
                        ? (s.overall_attendance >= 75 ? 'var(--success)' : 'var(--danger)')
                        : (s.est_cgpa >= 9 ? 'var(--primary)' : 'var(--text-main)');
                    const medal = rankEmojis[i] || `#${i + 1}`;
                    
                    // Check if this row is the current user
                    const isMe = s.net_id && myNetId && s.net_id.toUpperCase() === myNetId;
                    const bgStyle = isMe ? 'var(--glass)' : (i === 0 ? 'rgba(255,170,0,0.08)' : 'var(--glass)');
                    const borderStyle = isMe ? '2px solid var(--primary)' : (i === 0 ? '1px solid rgba(255,170,0,0.3)' : '1px solid var(--glass-border)');
                    const shadowStyle = isMe ? 'box-shadow: 0 0 15px rgba(255,170,0,0.3);' : '';
                    const idTag = isMe ? 'id="my-lb-row"' : '';
                    
                    return `
                    <div ${idTag} class="image-card fade-in-up" style="transform: none; display: flex; align-items: center; gap: 20px; padding: 20px; margin-bottom: 12px; background: ${bgStyle}; border: ${borderStyle}; ${shadowStyle}">
                        <div style="font-size: 2rem; min-width: 40px; text-align: center;">${medal}</div>
                        <div style="flex: 1; min-width: 0;">
                            <div style="font-family: 'Montserrat', sans-serif; font-weight: 900; font-size: 1rem; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${(s.name || 'Student').toUpperCase()} ${isMe ? '<span style="color: var(--primary); font-size: 0.8rem;">(YOU)</span>' : ''}</div>
                            <div style="font-size: 0.8rem; color: var(--text-sub); margin-top: 3px;">Reg No: <b style="color: var(--primary);">${(s.register_no || s.net_id || '—').toUpperCase()}</b></div>
                        </div>
                        <div style="font-family: 'Montserrat', sans-serif; font-weight: 900; font-size: 1.3rem; color: ${color}; white-space: nowrap;">${val}</div>
                    </div>`;
                }).join('');

                // Auto-scroll to the user's row if it exists
                setTimeout(() => {
                    const myRow = document.getElementById('my-lb-row');
                    if (myRow) myRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 400);

            } catch (e) {
                list.innerHTML = '<div style="text-align:center; color: var(--danger); padding: 40px;">Could not load leaderboard. Is the server running?</div>';
            }
        }

        // ============ PROJECT HUB ============
        async function loadProjects() {
            const list = document.getElementById('ph-list');
            if (!list) return;
            list.innerHTML = '<div class="css-loader" style="margin: 40px auto;"></div>';
            try {
                const res = await fetch(`${BACKEND_URL}/api/projects`);
                const projects = await res.json();
                const staticCards = `
                <div class="image-card fade-in-up" style="transform: none; text-align: left; background: rgba(255,170,0,0.05); border: 1px solid rgba(255,170,0,0.2);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                        <h3 style="color: var(--primary); margin: 0; font-size: 1.3rem; font-family: 'Montserrat', sans-serif;">AI-Powered Medical Diagnosis</h3>
                        <span style="background: rgba(255,170,0,0.2); padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; color: var(--primary); font-weight: bold; white-space: nowrap;">🔥 FEATURED</span>
                    </div>
                    <p style="color: var(--text-sub); line-height: 1.6; font-size: 0.95rem; margin-bottom: 15px;">A full-stack diagnostic tool using quantized LLMs to predict diseases from symptomatic inputs in real-time.</p>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px;">
                        <span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">Next.js</span>
                        <span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">PyTorch</span>
                        <span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">FastAPI</span>
                    </div>
                </div>`;

                const dynamicCardsHTML = projects.map(p => {
                    const techTags = (p.tech_stack || '').split(',').filter(t => t.trim()).map(t =>
                        `<span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">${t.trim()}</span>`
                    ).join('');
                    const links = [
                        p.github_url ? `<a href="${p.github_url}" target="_blank" style="color: var(--primary); font-weight: bold; font-size: 0.9rem;">GitHub ↗</a>` : '',
                        p.demo_url ? `<a href="${p.demo_url}" target="_blank" style="color: #62d5ff; font-weight: bold; font-size: 0.9rem;">Live Demo →</a>` : ''
                    ].filter(Boolean).join('<span style="color: var(--text-sub); padding: 0 10px;">|</span>');
                    return `
                    <div class="image-card fade-in-up" style="transform: none; text-align: left;">
                        <h3 style="color: var(--text-main); margin: 0 0 8px 0; font-size: 1.15rem; font-family: 'Montserrat', sans-serif;">${p.title}</h3>
                        ${p.submitted_by ? `<div style="font-size:0.8rem; color: var(--text-sub); margin-bottom: 10px;">By <b style="color: var(--primary);">${p.submitted_by}</b> · ${p.net_id ? p.net_id.toUpperCase() : ''}</div>` : ''}
                        <p style="color: var(--text-sub); font-size: 0.9rem; margin-bottom: 12px; line-height: 1.5;">${p.description || ''}</p>
                        ${techTags ? `<div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px;">${techTags}</div>` : ''}
                        ${links ? `<div style="display: flex; align-items: center; gap: 5px;">${links}</div>` : ''}
                    </div>`;
                }).join('');

                const placeholder = `
                <div class="image-card fade-in-up" style="transform: none; text-align: center; opacity: 0.6; border: 1px dashed var(--glass-border); padding: 35px;">
                    <h3 style="color: var(--text-sub); margin: 0 0 10px 0; font-style: italic; font-size: 1rem;">Your Project Could Be Here!</h3>
                    <p style="color: var(--text-sub); font-size: 0.85rem; margin: 0;">Click "+ Submit Your Project" to get featured.</p>
                </div>`;

                list.innerHTML = staticCards + dynamicCardsHTML + placeholder;
            } catch (e) {
                list.innerHTML = `<div class="image-card" style="text-align:center; color: var(--danger); padding: 40px;">Could not load projects. Is the server running?</div>`;
            }
        }

        // ============ IMAGE COMPRESSION ============
        async function compressImage(file) {
            return new Promise((resolve, reject) => {
                if (!file) return resolve('');
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = event => {
                    const img = new Image();
                    img.src = event.target.result;
                    img.onload = () => {
                        const canvas = document.createElement('canvas');
                        const MAX_WIDTH = 600;
                        const scaleSize = MAX_WIDTH / img.width;
                        canvas.width = MAX_WIDTH;
                        canvas.height = img.height * scaleSize;
                        
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                        
                        // Compress to 0.7 quality JPEG
                        const compressedBase64 = canvas.toDataURL('image/jpeg', 0.7);
                        resolve(compressedBase64);
                    }
                };
                reader.onerror = error => reject(error);
            });
        }

        // ============ CAMPUS MARKET ============
        let allMarketItems = [];
        let currentMarketCategory = 'All';

        function switchMarketCategory(cat, el) {
            document.querySelectorAll('#market-tabs .tab-btn').forEach(b => b.classList.remove('active'));
            el.classList.add('active');
            currentMarketCategory = cat;
            renderMarketplace();
        }

        async function loadMarketplace() {
            const list = document.getElementById('market-list');
            if (!list) return;
            list.innerHTML = '<div class="css-loader" style="margin: 40px auto;"></div>';
            try {
                const res = await fetch(`${BACKEND_URL}/api/marketplace`);
                allMarketItems = await res.json();
                renderMarketplace();
            } catch (e) {
                list.innerHTML = `<div class="image-card" style="text-align:center; color: var(--danger); padding: 40px;">Could not load marketplace.</div>`;
            }
        }

        function renderMarketplace() {
            const list = document.getElementById('market-list');
            if (!list) return;

            const filteredItems = currentMarketCategory === 'All' ? allMarketItems : allMarketItems.filter(i => i.category === currentMarketCategory);

            if (filteredItems.length === 0) {
                list.innerHTML = `
                <div class="image-card fade-in-up" style="transform: none; text-align: center; opacity: 0.6; border: 1px dashed var(--glass-border); padding: 35px;">
                    <h3 style="color: var(--text-sub); margin: 0 0 10px 0; font-style: italic; font-size: 1rem;">No items in this category yet.</h3>
                    <p style="color: var(--text-sub); font-size: 0.85rem; margin: 0;">Click "+ Sell an Item" to be the first!</p>
                </div>`;
                return;
            }

            const myNetId = getCurrentNetId();
            list.innerHTML = filteredItems.map(p => {
                const phoneWa = p.phone_no ? p.phone_no.replace(/\D/g, '') : '';
                const waLink = phoneWa ? `https://wa.me/${phoneWa}?text=Hi! I saw your "${p.title}" ad on SRM Student Hub.` : '';
                const formatTime = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';
                const isOwner = myNetId && p.net_id && myNetId === (p.net_id || '').toLowerCase();
                
                return `
                <div class="image-card fade-in-up" style="transform: none; text-align: left; position: relative; padding: 20px;">
                    <span style="position: absolute; top: 20px; right: 20px; background: rgba(255,255,255,0.1); padding: 5px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: bold; color: #fff;">${p.category || 'Item'}</span>
                    
                    <h3 style="color: var(--text-main); margin: 0 0 5px 0; font-size: 1.25rem; font-family: 'Montserrat', sans-serif; padding-right: 80px;">${p.title}</h3>
                    <div style="font-size:0.8rem; color: var(--text-sub); margin-bottom: 12px;">By <b style="color: var(--primary);">${p.seller_name}</b> &bull; ${formatTime}</div>
                    
                    ${p.image_url ? `<img src="${p.image_url}" alt="${p.title}" style="max-height: 250px; width: 100%; object-fit: cover; border-radius: 10px; margin-bottom: 15px; border: 1px solid var(--glass-border);" onerror="this.style.display='none'">` : ''}
                    
                    <p style="color: var(--text-sub); font-size: 0.95rem; margin-bottom: 15px; line-height: 1.5;">${p.description || ''}</p>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--glass-border); padding-top: 15px;">
                        <span style="font-size: 1.2rem; font-weight: 900; color: #62d5ff; font-family: 'Montserrat', sans-serif;">${p.price ? p.price : 'DM for price'}</span>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            ${isOwner ? `<button onclick="deleteMarketItem(${p.id})" style="background: rgba(255,68,68,0.15); border: 1px solid rgba(255,68,68,0.4); color: #ff4444; padding: 8px 14px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 0.85rem;">🗑️ Delete</button>` : ''}
                            ${waLink ? `<a href="${waLink}" target="_blank" style="background: #25D366; color: #fff; font-weight: bold; padding: 8px 16px; border-radius: 10px; text-decoration: none; font-size: 0.9rem; display: flex; align-items: center; gap: 8px;"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12 21.826A9.826 9.826 0 1 1 21.826 12 9.837 9.837 0 0 1 12 21.826M12 2C6.477 2 2 6.477 2 12c0 1.761.458 3.425 1.282 4.881L2 22l5.253-1.252A9.974 9.974 0 0 0 12 22c5.523 0 10-4.477 10-10S17.523 2 12 2"/></svg> Contact</a>` : ''}
                        </div>
                    </div>
                </div>`;
            }).join('');
        }

        async function submitMarketItem() {
            const title = document.getElementById('market-title').value.trim();
            const categoryElement = document.getElementById('market-category');
            const category = categoryElement.options[categoryElement.selectedIndex].value;
            const phone_no = document.getElementById('market-phone').value.trim();
            const status = document.getElementById('market-status');
            const imageFile = document.getElementById('market-image-file')?.files[0];
            
            if (!title || !category || !phone_no) { 
                status.style.color = 'var(--danger)'; status.innerText = 'Title, Category, and Phone are required!'; 
                return; 
            }

            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const regNoRaw = document.getElementById('srm-reg')?.value || profile.regNo || '';
            const netId = regNoRaw.split('@')[0] || '';

            status.style.color = 'var(--primary)'; status.innerText = 'Compressing image...';
            let image_url = '';
            try {
                if (imageFile) image_url = await compressImage(imageFile);
            } catch(e) { console.error("Compression failed", e); }

            status.style.color = 'var(--primary)'; status.innerText = 'Posting Item...';
            try {
                const res = await fetch(`${BACKEND_URL}/api/marketplace/submit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title, category, phone_no,
                        description: document.getElementById('market-desc').value,
                        price: document.getElementById('market-price').value,
                        image_url: image_url,
                        seller_name: profile.name || 'Student',
                        net_id: netId
                    })
                });
                const result = await res.json();
                if (result.success) {
                    status.style.color = 'var(--success)'; status.innerText = '✅ Item Posted!';
                    ['market-title','market-desc','market-price','market-phone'].forEach(id => document.getElementById(id).value = '');
                    const label = document.querySelector('label[for="market-image-file"]');
                    if(label) label.innerHTML = '📷 Click to select a photo from your device (Max 5MB) <input type="file" id="market-image-file" accept="image/*" style="display: none;">';
                    document.getElementById('market-category').selectedIndex = 0;
                    setTimeout(() => { document.getElementById('marketSubmitModal').style.display = 'none'; loadMarketplace(); }, 1500);
                } else {
                    status.style.color = 'var(--danger)'; status.innerText = '❌ ' + result.error;
                }
            } catch(e) {
                status.style.color = 'var(--danger)'; status.innerText = '❌ Could not connect to server.';
            }
        }

        async function deleteMarketItem(id) {
            if (!confirm('Are you sure you want to delete this listing?')) return;
            const netId = getCurrentNetId();
            try {
                const res = await fetch(`${BACKEND_URL}/api/marketplace/delete/${id}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ net_id: netId })
                });
                const result = await res.json();
                if (result.success) { loadMarketplace(); }
                else { alert(result.error || 'Could not delete item.'); }
            } catch(e) { alert('Connection error.'); }
        }

        // ============ CAMPUS WALL ============
        async function loadWall() {
            const list = document.getElementById('wall-list');
            if (!list) return;
            list.innerHTML = '<div class="css-loader" style="margin: 40px auto;"></div>';
            try {
                const res = await fetch(`${BACKEND_URL}/api/wall`);
                const posts = await res.json();
                
                if (posts.length === 0) {
                    list.innerHTML = '<div style="text-align:center; padding: 40px; color: var(--text-sub);">No confessions yet. Be the first!</div>';
                    return;
                }

                list.innerHTML = posts.map(p => {
                    const formatTime = p.created_at ? new Date(p.created_at).toLocaleString() : '';
                    return `
                    <div class="image-card fade-in-up" id="post-${p.id}" style="transform: none; text-align: left; padding: 18px;">
                        <div style="font-size: 0.8rem; color: var(--text-sub); margin-bottom: 8px; display: flex; justify-content: space-between;">
                            <span>Anonymous Fox 🦊</span>
                            <span>${formatTime}</span>
                        </div>
                        <p style="color: var(--text-main); font-size: 1.05rem; line-height: 1.5; margin: 0 0 15px 0;">${p.message}</p>
                        <div style="display: flex; gap: 15px;">
                            <button onclick="likeWall(${p.id})" style="background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); color: var(--text-main); border-radius: 20px; padding: 5px 15px; cursor: pointer; display: flex; align-items: center; gap: 5px;"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg> <span id="like-count-${p.id}">${p.likes || 0}</span></button>
                        </div>
                    </div>`;
                }).join('');
            } catch (e) {
                list.innerHTML = `<div style="text-align:center; color: var(--danger); padding: 40px;">Could not load Wall.</div>`;
            }
        }

        async function submitWall() {
            const input = document.getElementById('wall-input');
            const status = document.getElementById('wall-status');
            const message = input.value.trim();
            if(!message) return;

            input.disabled = true;
            try {
                const res = await fetch(`${BACKEND_URL}/api/wall/submit`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message })
                });
                const result = await res.json();
                if(result.success) {
                    input.value = '';
                    status.innerText = '';
                    loadWall();
                } else {
                    status.innerText = 'Failed to post.';
                }
            } catch(e) { status.innerText = 'Connection error.'; }
            input.disabled = false;
        }

        async function likeWall(id) {
            try {
                // Optimistic UI update
                const countEl = document.getElementById(`like-count-${id}`);
                const btn = countEl.parentElement;
                countEl.innerText = parseInt(countEl.innerText) + 1;
                btn.style.color = 'var(--primary)';
                btn.style.borderColor = 'var(--primary)';
                btn.style.pointerEvents = 'none';

                await fetch(`${BACKEND_URL}/api/wall/like/${id}`, { method: 'POST' });
            } catch(e) { console.error('Like failed'); }
        }

        // ============ CAB SHARING ============
        async function loadCabs() {
            const list = document.getElementById('cabs-list');
            if (!list) return;
            list.innerHTML = '<div class="css-loader" style="margin: 40px auto;"></div>';
            try {
                const res = await fetch(`${BACKEND_URL}/api/cabs`);
                const cabs = await res.json();
                
                if (cabs.length === 0) {
                    list.innerHTML = `
                    <div class="image-card" style="text-align: center; opacity: 0.6; border: 1px dashed var(--glass-border); padding: 35px;">
                        <h3 style="color: var(--text-sub); margin: 0 0 10px 0; font-style: italic;">No active rides.</h3>
                        <p style="color: var(--text-sub); font-size: 0.85rem; margin: 0;">Post a ride if you're traveling soon!</p>
                    </div>`;
                    return;
                }

                const myNetId = getCurrentNetId();
                list.innerHTML = cabs.map(p => {
                    const phoneWa = p.phone_no ? p.phone_no.replace(/\D/g, '') : '';
                    const waLink = phoneWa ? `https://wa.me/${phoneWa}?text=Hi! I saw your Cab ride to ${p.destination} on SRM Hub.` : '';
                    const formattedDate = new Date(p.travel_date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
                    const isOwner = myNetId && p.net_id && myNetId === (p.net_id || '').toLowerCase();
                    
                    return `
                    <div class="image-card fade-in-up" style="transform: none; text-align: left; padding: 20px; border-left: 4px solid #00cc66;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <div style="font-size: 0.8rem; color: var(--primary); text-transform: uppercase; font-weight: bold; letter-spacing: 1px; margin-bottom: 5px;">TO: ${p.destination}</div>
                                <h3 style="margin: 0 0 10px 0; color: var(--text-main); font-size: 1.2rem;">${formattedDate} &bull; ${p.travel_time}</h3>
                                <div style="font-size: 0.9rem; color: var(--text-sub); margin-bottom: 15px;"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 5px;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg> ${p.spots || 'Spots available'}</div>
                                <div style="font-size: 0.8rem; color: #888;">Posted by ${p.creator_name || 'Student'}</div>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 8px; align-items: flex-end;">
                                ${waLink ? `<a href="${waLink}" target="_blank" style="background: #25D366; color: #fff; text-decoration: none; padding: 10px 15px; border-radius: 12px; font-weight: bold; font-size: 0.9rem; white-space: nowrap;">Chat ↗</a>` : ''}
                                ${isOwner ? `<button onclick="deleteCab(${p.id})" style="background: rgba(255,68,68,0.15); border: 1px solid rgba(255,68,68,0.4); color: #ff4444; padding: 6px 12px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 0.8rem;">🗑️ Delete</button>` : ''}
                            </div>
                        </div>
                    </div>`;
                }).join('');
            } catch (e) { list.innerHTML = `<div style="text-align:center; color: var(--danger); padding: 40px;">Could not load cabs.</div>`; }
        }

        async function submitCab() {
            const destination = document.getElementById('cab-dest').value.trim();
            const travel_date = document.getElementById('cab-date').value;
            const travel_time = document.getElementById('cab-time').value;
            const spots = document.getElementById('cab-spots').value.trim();
            const phone_no = document.getElementById('cab-phone').value.trim();
            const status = document.getElementById('cab-status');
            
            if (!destination || !travel_date || !travel_time || !phone_no) { 
                status.style.color = 'var(--danger)'; status.innerText = 'All fields except spots are required!'; 
                return; 
            }

            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const regNoRaw = document.getElementById('srm-reg')?.value || profile.regNo || '';
            const netId = regNoRaw.split('@')[0] || '';

            status.style.color = 'var(--primary)'; status.innerText = 'Posting...';
            try {
                const res = await fetch(`${BACKEND_URL}/api/cabs/submit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        destination, travel_date, travel_time, spots, phone_no,
                        creator_name: profile.name || 'Student',
                        net_id: netId
                    })
                });
                const result = await res.json();
                if (result.success) {
                    status.style.color = 'var(--success)'; status.innerText = '✅ Ride Request Posted!';
                    ['cab-dest','cab-date','cab-time','cab-spots','cab-phone'].forEach(id => document.getElementById(id).value = '');
                    setTimeout(() => { document.getElementById('cabSubmitModal').style.display = 'none'; loadCabs(); }, 1500);
                } else { status.style.color = 'var(--danger)'; status.innerText = '❌ ' + result.error; }
            } catch(e) { status.style.color = 'var(--danger)'; status.innerText = '❌ Connection error.'; }
        }

        // ============ EVENTS & CLUB RADAR ============
        async function loadEvents() {
            const list = document.getElementById('events-list');
            if (!list) return;
            list.innerHTML = '<div class="css-loader" style="margin: 40px auto;"></div>';
            try {
                const res = await fetch(`${BACKEND_URL}/api/events`);
                const events = await res.json();
                
                if (events.length === 0) {
                    list.innerHTML = `
                    <div class="image-card" style="text-align: center; opacity: 0.6; border: 1px dashed var(--glass-border); padding: 35px;">
                        <h3 style="color: var(--text-sub); margin: 0 0 10px 0; font-style: italic;">No upcoming events.</h3>
                        <p style="color: var(--text-sub); font-size: 0.85rem; margin: 0;">Is your club hosting something? Post it here!</p>
                    </div>`;
                    return;
                }

                list.innerHTML = events.map(p => {
                    const formattedDate = p.event_date ? new Date(p.event_date).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }) : 'Date TBD';
                    
                    return `
                    <div class="image-card fade-in-up" style="transform: none; text-align: left; padding: 0; overflow: hidden; position: relative;">
                        ${p.image_url ? `<div style="width: 100%; height: 200px; overflow: hidden; background: #111;"><img src="${p.image_url}" style="width: 100%; height: 100%; object-fit: cover; opacity: 0.8;" onerror="this.style.display='none'"></div>` : ''}
                        
                        <div style="padding: 20px;">
                            <span style="background: rgba(230,0,115,0.2); color: #ff3399; font-size: 0.75rem; font-weight: bold; padding: 4px 10px; border-radius: 12px; text-transform: uppercase;">${p.club_name}</span>
                            <h3 style="margin: 10px 0 5px 0; color: var(--text-main); font-size: 1.4rem; font-family: 'Montserrat', sans-serif;">${p.event_title}</h3>
                            <div style="font-size: 0.95rem; color: var(--primary); margin-bottom: 15px; font-weight: bold;">🗓️ ${formattedDate}</div>
                            
                            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--glass-border); padding-top: 15px; margin-top: 10px;">
                                <div style="font-size: 0.8rem; color: var(--text-sub);">Posted by ${p.created_by || 'Student'}</div>
                                ${p.registration_link ? `<a href="${p.registration_link}" target="_blank" style="background: #e60073; color: #fff; text-decoration: none; padding: 8px 20px; border-radius: 12px; font-weight: bold; font-size: 0.9rem;">Register ↗</a>` : ''}
                            </div>
                        </div>
                    </div>`;
                }).join('');
            } catch (e) { list.innerHTML = `<div style="text-align:center; color: var(--danger); padding: 40px;">Could not load events.</div>`; }
        }

        async function submitEvent() {
            const club_name = document.getElementById('event-club').value.trim();
            const event_title = document.getElementById('event-title').value.trim();
            const event_date = document.getElementById('event-date').value;
            const registration_link = document.getElementById('event-link').value.trim();
            const imageFile = document.getElementById('event-image-file')?.files[0];
            const status = document.getElementById('event-status');
            
            if (!club_name || !event_title || !event_date) { 
                status.style.color = 'var(--danger)'; status.innerText = 'Club name, Title, and Date are required!'; 
                return; 
            }

            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const regNoRaw = document.getElementById('srm-reg')?.value || profile.regNo || '';
            const netId = regNoRaw.split('@')[0] || '';

            status.style.color = '#e60073'; status.innerText = 'Compressing image...';
            let image_url = '';
            try {
                if (imageFile) image_url = await compressImage(imageFile);
            } catch(e) { console.error("Compression failed", e); }

            status.style.color = '#e60073'; status.innerText = 'Posting Event...';
            try {
                const res = await fetch(`${BACKEND_URL}/api/events/submit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        club_name, event_title, event_date, registration_link, image_url,
                        created_by: profile.name || 'Student',
                        net_id: netId
                    })
                });
                const result = await res.json();
                if (result.success) {
                    status.style.color = 'var(--success)'; status.innerText = '✅ Event Posted!';
                    ['event-club','event-title','event-date','event-link'].forEach(id => document.getElementById(id).value = '');
                    const label = document.querySelector('label[for="event-image-file"]');
                    if(label) label.innerHTML = '🖼️ Click to upload Event Poster from device <input type="file" id="event-image-file" accept="image/*" style="display: none;">';
                    setTimeout(() => { document.getElementById('eventSubmitModal').style.display = 'none'; loadEvents(); }, 1500);
                } else { status.style.color = 'var(--danger)'; status.innerText = '❌ ' + result.error; }
            } catch(e) { status.style.color = 'var(--danger)'; status.innerText = '❌ Connection error.'; }
        }

        async function submitProject() {
            const title = document.getElementById('ph-title').value.trim();
            const status = document.getElementById('ph-status');
            if (!title) { status.style.color = 'var(--danger)'; status.innerText = 'Title is required!'; return; }

            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const regNoRaw = document.getElementById('srm-reg')?.value || '';
            const netId = regNoRaw.split('@')[0] || profile.regNo?.split('@')[0] || '';

            status.style.color = 'var(--primary)'; status.innerText = 'Submitting...';
            try {
                const res = await fetch(`${BACKEND_URL}/api/projects/submit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title, description: document.getElementById('ph-desc').value,
                        tech_stack: document.getElementById('ph-tech').value,
                        github_url: document.getElementById('ph-github').value,
                        demo_url: document.getElementById('ph-demo').value,
                        submitted_by: profile.name || 'Student',
                        net_id: netId
                    })
                });
                const result = await res.json();
                if (result.success) {
                    status.style.color = 'var(--success)'; status.innerText = '✅ Project submitted!';
                    ['ph-title','ph-desc','ph-tech','ph-github','ph-demo'].forEach(id => document.getElementById(id).value = '');
                    setTimeout(() => { document.getElementById('projectSubmitModal').style.display = 'none'; loadProjects(); }, 1500);
                } else {
                    status.style.color = 'var(--danger)'; status.innerText = '❌ ' + result.error;
                }
            } catch(e) {
                status.style.color = 'var(--danger)'; status.innerText = '❌ Could not connect to server.';
            }
        }

        async function deleteCab(id) {
            if (!confirm('Are you sure you want to delete this ride?')) return;
            const netId = getCurrentNetId();
            try {
                const res = await fetch(`${BACKEND_URL}/api/cabs/delete/${id}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ net_id: netId })
                });
                const result = await res.json();
                if (result.success) { loadCabs(); }
                else { alert(result.error || 'Could not delete ride.'); }
            } catch(e) { alert('Connection error.'); }
        }

        // ============ LOST & FOUND ============
        let allLFItems = [];
        let currentLFCategory = 'All';

        function switchLFCategory(cat, el) {
            document.querySelectorAll('#lf-tabs .tab-btn').forEach(b => b.classList.remove('active'));
            el.classList.add('active');
            currentLFCategory = cat;
            renderLostFound();
        }

        async function loadLostFound() {
            const list = document.getElementById('lf-list');
            if (!list) return;
            list.innerHTML = '<div class="css-loader" style="margin: 40px auto;"></div>';
            try {
                const res = await fetch(`${BACKEND_URL}/api/lostfound`);
                allLFItems = await res.json();
                renderLostFound();
            } catch (e) {
                list.innerHTML = `<div class="image-card" style="text-align:center; color: var(--danger); padding: 40px;">Could not load Lost & Found.</div>`;
            }
        }

        function renderLostFound() {
            const list = document.getElementById('lf-list');
            if (!list) return;

            const filtered = currentLFCategory === 'All' ? allLFItems : allLFItems.filter(i => i.category === currentLFCategory);
            const myNetId = getCurrentNetId();

            if (filtered.length === 0) {
                list.innerHTML = `
                <div class="image-card fade-in-up" style="transform: none; text-align: center; opacity: 0.6; border: 1px dashed var(--glass-border); padding: 35px;">
                    <h3 style="color: var(--text-sub); margin: 0 0 10px 0; font-style: italic; font-size: 1rem;">No items reported yet.</h3>
                    <p style="color: var(--text-sub); font-size: 0.85rem; margin: 0;">Click "+ Report Item" to post.</p>
                </div>`;
                return;
            }

            list.innerHTML = filtered.map(p => {
                const formatTime = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';
                const isOwner = myNetId && p.net_id && myNetId === (p.net_id || '').toLowerCase();
                const catColor = p.category === 'Lost' ? '#ff4444' : '#00cc66';
                const catIcon = p.category === 'Lost' ? '❓' : '✅';

                return `
                <div class="image-card fade-in-up" style="transform: none; text-align: left; position: relative; padding: 20px; border-left: 4px solid ${catColor};">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                        <span style="background: ${catColor}22; color: ${catColor}; padding: 4px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: bold; text-transform: uppercase;">${catIcon} ${p.category || 'Item'}</span>
                        ${isOwner ? `<button onclick="deleteLostFound(${p.id})" style="background: rgba(255,68,68,0.15); border: 1px solid rgba(255,68,68,0.4); color: #ff4444; padding: 5px 12px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.8rem;">🗑️ Delete</button>` : ''}
                    </div>
                    
                    <h3 style="color: var(--text-main); margin: 0 0 5px 0; font-size: 1.2rem; font-family: 'Montserrat', sans-serif;">${p.title}</h3>
                    <div style="font-size:0.8rem; color: var(--text-sub); margin-bottom: 10px;">By <b style="color: var(--primary);">${p.poster_name}</b> &bull; ${formatTime}</div>
                    
                    ${p.location ? `<div style="font-size: 0.85rem; color: var(--primary); margin-bottom: 10px;"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 5px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${p.location}</div>` : ''}
                    
                    ${p.image_url ? `<img src="${p.image_url}" alt="${p.title}" style="max-height: 250px; width: 100%; object-fit: cover; border-radius: 10px; margin-bottom: 12px; border: 1px solid var(--glass-border);" onerror="this.style.display='none'">` : ''}
                    
                    <p style="color: var(--text-sub); font-size: 0.95rem; line-height: 1.5; margin: 0;">${p.description || ''}</p>
                </div>`;
            }).join('');
        }

        async function submitLostFound() {
            const title = document.getElementById('lf-title').value.trim();
            const catEl = document.getElementById('lf-category');
            const category = catEl.options[catEl.selectedIndex].value;
            const status = document.getElementById('lf-status');
            const imageFile = document.getElementById('lf-image-file')?.files[0];

            if (!title || !category) {
                status.style.color = 'var(--danger)'; status.innerText = 'Item name and category are required!';
                return;
            }

            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const netId = getCurrentNetId();

            let image_url = '';
            try {
                status.style.color = 'var(--primary)'; status.innerText = 'Processing...';
                if (imageFile) image_url = await compressImage(imageFile);
            } catch(e) { console.error('Compression failed', e); }

            status.style.color = 'var(--primary)'; status.innerText = 'Posting...';
            try {
                const res = await fetch(`${BACKEND_URL}/api/lostfound/submit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title, category,
                        description: document.getElementById('lf-desc').value,
                        location: document.getElementById('lf-location').value,
                        image_url: image_url,
                        poster_name: profile.name || 'Student',
                        net_id: netId
                    })
                });
                const result = await res.json();
                if (result.success) {
                    status.style.color = 'var(--success)'; status.innerText = '✅ Item Reported!';
                    ['lf-title','lf-desc','lf-location'].forEach(id => document.getElementById(id).value = '');
                    catEl.selectedIndex = 0;
                    setTimeout(() => { document.getElementById('lfSubmitModal').style.display = 'none'; loadLostFound(); }, 1500);
                } else {
                    status.style.color = 'var(--danger)'; status.innerText = '❌ ' + result.error;
                }
            } catch(e) {
                status.style.color = 'var(--danger)'; status.innerText = '❌ Connection error.';
            }
        }

        async function deleteLostFound(id) {
            if (!confirm('Are you sure you want to delete this report?')) return;
            const netId = getCurrentNetId();
            try {
                const res = await fetch(`${BACKEND_URL}/api/lostfound/delete/${id}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ net_id: netId })
                });
                const result = await res.json();
                if (result.success) { loadLostFound(); }
                else { alert(result.error || 'Could not delete.'); }
            } catch(e) { alert('Connection error.'); }
        }

        // ============ AUTO-NOTIFICATION PROMPT FOR ALL USERS ============
        window.addEventListener('load', () => {
            setTimeout(() => {
                if ('Notification' in window && Notification.permission === 'default') {
                    Notification.requestPermission().then(permission => {
                        if (permission === 'granted') {
                            new Notification('SRM Student Hub 🎓', {
                                body: 'Notifications enabled! You will get updates on exams and deadlines.',
                                icon: '/icon-192.png'
                            });
                        }
                    });
                }
            }, 2000); // Ask after 2 sec so the user sees the app first
        });


    