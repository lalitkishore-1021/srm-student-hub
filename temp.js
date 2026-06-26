
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
            let logoTaps = 0;
            let logoTapTimer = null;
            logoTrigger.addEventListener('click', () => {
                logoTaps++;
                clearTimeout(logoTapTimer);
                if (logoTaps >= 3) {
                    logoTaps = 0;
                    triggerConfetti();
                    showNotification("🎉 You found the secret! Built with love by Lalit Kishore.");
                } else {
                    logoTapTimer = setTimeout(() => { logoTaps = 0; }, 2000);
                    if (logoTaps === 1 && deferredPrompt) openInstallModal();
                }
            });
        }
        
        function triggerConfetti() {
            let canvas = document.getElementById('confetti-canvas');
            if (!canvas) {
                canvas = document.createElement('canvas');
                canvas.id = 'confetti-canvas';
                document.body.appendChild(canvas);
            }
            if (!window.confetti) {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js';
                script.onload = () => confetti({ particleCount: 150, spread: 100, origin: { y: 0.6 } });
                document.body.appendChild(script);
            } else {
                confetti({ particleCount: 150, spread: 100, origin: { y: 0.6 } });
            }
            setTimeout(() => { if(canvas) canvas.remove(); }, 5000);
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
            return false;
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
            
            // Liquid indicator animation
            const indicator = document.getElementById('nav-indicator');
            if (indicator && element) {
                const navRect = document.querySelector('.app-nav').getBoundingClientRect();
                const elRect = element.getBoundingClientRect();
                const relativeLeft = elRect.left - navRect.left;
                indicator.style.left = `${relativeLeft + (elRect.width * 0.25)}px`;
                indicator.style.width = `${elRect.width * 0.5}px`;
            }
            
            switchView(viewId);
        }

        window.addEventListener('load', () => {
            setTimeout(() => {
                const activeNav = document.querySelector('.nav-item.active');
                if (activeNav) switchNav('home-view', activeNav);
            }, 100);
        });

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

            // Inject 3D Avatar
            const avatarImg = document.getElementById('id-avatar-img');
            const fallback = document.getElementById('id-avatar-fallback');
            if (avatarImg && profile.regNo) {
                // Use DiceBear Micah API (3D style like Snapchat) with a custom aesthetic background
                avatarImg.src = `https://api.dicebear.com/7.x/micah/svg?seed=${profile.regNo}&backgroundColor=b6e3f4`;
                avatarImg.style.display = 'block';
                if(fallback) fallback.style.display = 'none';
            }

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
                if (faPhoneEl) faPhoneEl.innerText = ' ' + (profile.fa_phone || 'N/A');
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
                if (aaPhoneEl) aaPhoneEl.innerText = ' ' + (profile.aa_phone || 'N/A');
                if (aaCallBtn && profile.aa_phone) {
                    aaCallBtn.href = 'tel:' + profile.aa_phone;
                } else if (aaCallBtn) {
                    aaCallBtn.style.display = 'none';
                }
            }
        }

        function loadSavedData() {
            try {
                const savedProfile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
                const savedAtt = JSON.parse(localStorage.getItem('squadAttendance') || '[]');
                const savedMarks = JSON.parse(localStorage.getItem('squadMarks') || '[]');
                const savedTT = JSON.parse(localStorage.getItem('squadTimetable') || '{}');

                try { renderProfile(savedProfile); } catch (e) { console.error("Profile render failed:", e); }
                try { renderAttendance(savedAtt); } catch (e) { console.error("Attendance render failed:", e); }
                try { renderMarks(savedMarks); } catch (e) { console.error("Marks render failed:", e); }
                try { renderTimetable(savedTT); } catch (e) { console.error("Timetable render failed:", e); }
            } catch (e) {
                console.error("Critical error loading saved data:", e);
            }
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
                toast.innerHTML = success ? ` Data Synced Successfully` : ` Background Sync Failed`;
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

            document.getElementById('login-form-container').style.display = 'none';
            document.getElementById('login-loader-container').style.display = 'flex';

            let secondsPassed = 0;
            statusText.innerHTML = ` Connecting to Academia... <span style="font-family: inherit; font-size: 1.1rem; color: #fff; background: rgba(255,170,0,0.2); padding: 2px 8px; border-radius: 6px;">0s</span>`;
            statusText.style.color = "var(--primary)";
            
            const tips = [
                " Did you know? The library has a massive collection of e-books available for free.",
                " Pro Tip: Maintaining above 8.5 CGPA makes placement drives much easier.",
                " Fun Fact: SRM was founded in 1985 and has grown into a massive global campus.",
                " Hack: Use the Attendance Planner to exactly know how many classes you can bunk!",
                " Fact: The Tech Park canteen serves the best sandwiches on campus."
            ];
            let tipIndex = 0;

            let timerInterval = setInterval(() => {
                secondsPassed++;
                statusText.innerHTML = ` Syncing securely... <span style="font-family: inherit; font-size: 1.1rem; color: #fff; background: rgba(255,170,0,0.2); padding: 2px 8px; border-radius: 6px;">${secondsPassed}s</span>`;
                
                let prog = Math.min((secondsPassed / 50) * 100, 95);
                let pb = document.getElementById('login-progress-bar');
                if (pb) pb.style.width = prog + '%';

                if (secondsPassed % 5 === 0) {
                    tipIndex = (tipIndex + 1) % tips.length;
                    let tipEl = document.getElementById('login-tip');
                    if (tipEl) {
                        tipEl.style.opacity = '0';
                        setTimeout(() => {
                            tipEl.innerText = tips[tipIndex];
                            tipEl.style.opacity = '1';
                        }, 300);
                    }
                }
            }, 1000);

            try {
                const initRes = await fetch(`${BACKEND_URL}/api/start_session`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ regNo: regNo, pwd: pwd, batch: currentBatch })
                });

                const initData = await initRes.json();
                if (!initData.success) {
                    clearInterval(timerInterval);
                    statusText.innerText = ` ${initData.error}`;
                    statusText.style.color = "var(--danger)";
                    return;
                }

                const syncId = initData.sync_id;
                let result = null;

                // Polling loop
                while (true) {
                    await new Promise(r => setTimeout(r, 3000)); // wait 3 seconds
                    try {
                        const statusRes = await fetch(`${BACKEND_URL}/api/sync_status/${syncId}`);
                        const statusData = await statusRes.json();
                        
                        if (statusData.status === 'completed' || statusData.status === 'failed') {
                            result = statusData.result;
                            break;
                        }
                    } catch (err) {
                        console.warn("Polling error (will retry):", err);
                    }
                    
                    if (secondsPassed > 240) { // Hard limit 4 minutes
                        result = { success: false, error: "Sync timed out. Academia is too slow today." };
                        break;
                    }
                }

                clearInterval(timerInterval);

                if (!result || !result.success) {
                    statusText.innerText = ` ${result ? result.error : 'Unknown error'} (Failed after ${secondsPassed}s)`;
                    statusText.style.color = "var(--danger)";
                    return;
                }

                statusText.innerText = ` Success! Synced in ${secondsPassed} seconds.`;
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

                document.getElementById('login-progress-bar').style.width = '100%';

                setTimeout(() => {
                    document.getElementById('login-view').style.display = 'none';
                    let mc = document.getElementById('main-content');
                    mc.style.display = 'block';
                    mc.classList.add('content-visible');
                    document.getElementById('navButtons').style.display = 'flex';
                    document.querySelector('.site-header').style.display = 'flex';
                    document.querySelector('.app-nav').style.display = 'flex';
                }, 1500);

            } catch (e) {
                document.getElementById('login-form-container').style.display = 'block';
                document.getElementById('login-loader-container').style.display = 'none';
                clearInterval(timerInterval);
                alert(" Could not connect to backend server. Please try again.");
            }
        }

        async function backgroundSync() {
            const regNo = localStorage.getItem("syncRegNo");
            const pwd = localStorage.getItem("syncPwd");
            const batch = localStorage.getItem("syncBatch") || currentBatch;
            
            if (!regNo || !pwd) return; // Cannot auto sync

            showSyncToast();
            try {
                const initRes = await fetch(`${BACKEND_URL}/api/start_session`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ regNo, pwd, batch })
                });

                const initData = await initRes.json();
                if (!initData.success) {
                    hideSyncToast(false);
                    return;
                }
                
                const syncId = initData.sync_id;
                let result = null;
                let polls = 0;
                
                while (polls < 80) { // Max ~4 mins
                    await new Promise(r => setTimeout(r, 3000));
                    polls++;
                    try {
                        const statusRes = await fetch(`${BACKEND_URL}/api/sync_status/${syncId}`);
                        const statusData = await statusRes.json();
                        if (statusData.status === 'completed' || statusData.status === 'failed') {
                            result = statusData.result;
                            break;
                        }
                    } catch (err) {}
                }

                if (result && result.success) {
                    localStorage.setItem('lastSyncSuccessTime', Date.now().toString());
                    const banner = document.getElementById('sync-reminder-banner');
                    if (banner) banner.style.display = 'none';
                    
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
            let safeId = id ? id.toString().replace(/[^a-zA-Z0-9]/g, '') : 'unknown';
            if (!simulationState[safeId]) simulationState[safeId] = { bunked: 0, attended: 0 };
            if (action === 'bunk') simulationState[safeId].bunked++;
            else if (action === 'attend') simulationState[safeId].attended++;
            else if (action === 'reset') simulationState[safeId] = { bunked: 0, attended: 0 };
            renderAttendance(attendanceData);
        }

        function predictDateRange() {
            const start = document.getElementById('predict-start-date').value;
            const end = document.getElementById('predict-end-date').value;
            if (!start || !end) return alert('Please select both start and end dates.');
            
            const startDate = new Date(start);
            const endDate = new Date(end);
            if (endDate < startDate) return alert('End date must be after start date.');
            
            const ttDict = JSON.parse(localStorage.getItem('squadTimetable') || '{}');
            if(Object.keys(ttDict).length === 0) return alert('No timetable data available to predict leave. Please sync timetable first.');
            
            let daysToSimulate = [];
            let curr = new Date(startDate);
            while (curr <= endDate) {
                // Ignore Sundays (0) and Saturdays (6) if no classes usually
                if(curr.getDay() !== 0 && curr.getDay() !== 6) {
                    daysToSimulate.push(curr.getDay()); // 1 to 5 (Mon-Fri)
                }
                curr.setDate(curr.getDate() + 1);
            }
            
            let bunkCounts = {};
            daysToSimulate.forEach(dayIndex => {
                let dayOrder = dayIndex; // Basic mapping Mon=1, Tue=2, etc. (Can be improved with actual academic calendar if available)
                if (ttDict[dayOrder]) {
                    ttDict[dayOrder].forEach(session => {
                        if (session && session.title) {
                            let cId = session.title.replace(/[^a-zA-Z0-9]/g, '');
                            if(!bunkCounts[cId]) bunkCounts[cId] = 0;
                            bunkCounts[cId]++;
                        }
                    });
                }
            });
            
            Object.keys(bunkCounts).forEach(cId => {
                if (!simulationState[cId]) simulationState[cId] = { bunked: 0, attended: 0 };
                simulationState[cId].bunked += bunkCounts[cId];
            });
            
            renderAttendance(attendanceData);
            alert(`Simulated absence for ${daysToSimulate.length} working days based on your timetable!`);
        }

        function resetAllPredictions() {
            simulationState = {};
            renderAttendance(attendanceData);
        }

        function renderAttendance(attData) {
            const list = document.getElementById('attendance-list');
            if (!list) return;

            let html = '';
            let totalAtt = 0;
            let totalClasses = 0;
            attendanceData = attData || [];

            attendanceData.forEach(sub => {
                let name = sub.courseTitle || sub.name || "Unknown Subject";
                let rawId = sub.id || sub.courseCode || name;
                let safeId = rawId.toString().replace(/[^a-zA-Z0-9]/g, '');
                
                let sim = simulationState[safeId] || { bunked: 0, attended: 0 };
                let baseAttended = parseInt(sub.attended) || 0;
                let baseTotal = parseInt(sub.total) || 0;
                
                let attended = baseAttended + sim.attended;
                let total = baseTotal + sim.bunked + sim.attended;

                totalAtt += attended;
                totalClasses += total;

                const percentage = total === 0 ? 0 : ((attended / total) * 100).toFixed(1);
                const isGood = percentage >= 75;
                const barColor = isGood ? 'var(--success)' : 'var(--danger)';
                const cardStyleModifier = isGood ? 'border: 1px solid var(--glass-border);' : 'border: 1px solid var(--danger); box-shadow: 0 0 15px rgba(255, 68, 68, 0.2);';

                let marginValue = 0;
                let marginLabel = 'Margin';
                if (isGood) {
                    marginValue = Math.floor((attended - (0.75 * total)) / 0.75);
                    if (marginValue < 0) marginValue = 0;
                } else {
                    marginValue = Math.ceil(((0.75 * total) - attended) / 0.25);
                    marginLabel = 'Need';
                }

                html += `
                    <div class="image-card morph-card" oncontextmenu="handleLongPress(event, '${name}', 'attendance')" onmousedown="startLongPress(event, '${name}', 'attendance')" onmouseup="cancelLongPress()" onmouseleave="cancelLongPress()" ontouchstart="startLongPress(event, '${name}', 'attendance')" ontouchend="cancelLongPress()" ontouchcancel="cancelLongPress()" style="display: flex; align-items: center; justify-content: space-between; padding: 20px; margin-bottom: 15px; transition: all 0.3s; ${cardStyleModifier}">
                        <div style="flex: 1; padding-right: 15px;">
                            <h3 style="margin: 0 0 10px 0; color: #fff; font-family: 'Montserrat', sans-serif; font-size: 1rem; line-height: 1.3;">${name}</h3>
                            <div class="stat-text" style="color: #fff; font-weight: bold; margin-top: 10px;">${attended} / ${total} Attended</div>
                            <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; margin-top: 10px;">
                                <div style="width: ${percentage}%; height: 100%; background: ${barColor}; border-radius: 3px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1);"></div>
                            </div>
                        </div>
                        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.3); border-radius: 12px; padding: 15px; border: 1px solid ${isGood ? 'rgba(0,204,102,0.3)' : 'rgba(255,68,68,0.3)'}; min-width: 80px; text-align: center;">
                            <div style="font-size: 2rem; font-weight: 900; color: ${barColor}; line-height: 1;">${marginValue}</div>
                            <div style="font-size: 0.75rem; color: ${barColor}; font-weight: 600; text-transform: uppercase; margin-top: 4px; margin-bottom: 10px; letter-spacing: 1px;">${marginLabel}</div>
                            <div style="font-size: 1.3rem; font-family: 'Montserrat', sans-serif; font-weight: 900; color: ${barColor};">${percentage}%</div>
                        </div>
                    </div>
                `;
            });
            
            // Skeleton Morph transition
            const skeletons = list.querySelectorAll('.skeleton-card');
            if (skeletons.length > 0) {
                skeletons.forEach(s => s.classList.add('skeleton-morph'));
                setTimeout(() => {
                    list.innerHTML = html;
                }, 400); // Wait for fade out
            } else {
                list.innerHTML = html;
            }

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
                const creditEl = document.getElementById('home-credit-val');
                
                if (attEl) attEl.innerText = overallPerc + "%";
                if (courseEl) courseEl.innerText = attendanceData.length;
                if (attPercBadge) {
                    const op = parseFloat(overallPerc);
                    if (op >= 90) { attPercBadge.innerHTML = ' TOP 5%'; attPercBadge.style.color = 'var(--primary)'; }
                    else if (op >= 80) { attPercBadge.innerHTML = ' TOP 15%'; attPercBadge.style.color = '#fff'; }
                    else if (op < 75) { attPercBadge.innerHTML = ' RISK ZONE'; attPercBadge.style.color = 'var(--danger)'; }
                    else { attPercBadge.innerHTML = ' AVERAGE'; attPercBadge.style.color = 'var(--text-sub)'; }
                }
                // Calculate total credits from attendance data
                if (creditEl) {
                    let totalCredits = 0;
                    attendanceData.forEach(sub => {
                        totalCredits += parseFloat(sub.credits || 0);
                    });
                    if (totalCredits > 0) creditEl.innerText = totalCredits;
                }
            }
        }

        // ================= CGPA PREDICTOR LOGIC =================
        let cgpaState = {};

        function openCGPACalculator() {
            const marksData = JSON.parse(localStorage.getItem('squadMarks') || '[]');
            if(!marksData.length) return alert('No marks data available');
            
            cgpaState = {};
            let html = '';
            
            marksData.forEach((item, index) => {
                const course = item.courseTitle || item.CourseTitle || item.name || "Subject";
                let perfString = item['Test Performance'] || item.performance || item.marks || "";
                if (!perfString && typeof item === 'object') {
                    perfString = Object.values(item).filter(v => typeof v === 'string').join(' | ');
                }

                let subjectMax = 0; let subjectObtained = 0;
                const regex = /([A-Za-z0-9-]+)\/([0-9.]+)\s*\|\s*([0-9.]+)/g;
                let match;
                while ((match = regex.exec(perfString)) !== null) {
                    subjectMax += parseFloat(match[2]); 
                    subjectObtained += parseFloat(match[3]);
                }
                
                if (subjectMax === 0) return;
                
                let credits = item.credits !== undefined ? parseFloat(item.credits) : 3;
                let courseId = course.replace(/[^a-zA-Z0-9]/g, '') + index;
                
                cgpaState[courseId] = {
                    title: course,
                    internalObtained: subjectObtained,
                    internalMax: subjectMax,
                    targetPercent: 90,
                    credits: credits
                };

                html += `
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid var(--glass-border);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                        <div style="flex:1;">
                            <h4 style="margin:0 0 5px 0; color: #fff; font-size: 0.95rem;">${course}</h4>
                            <p style="margin:0; font-size:0.75rem; color: var(--text-sub);">Internal: ${subjectObtained.toFixed(1)} / ${subjectMax} &nbsp;|&nbsp; Credits: ${credits}</p>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-size: 0.8rem; color: var(--text-sub);">Target Grade:</span>
                        <span style="font-size: 0.9rem; color: var(--primary); font-weight: bold;" id="cgpa-target-label-${courseId}">A+</span>
                    </div>
                    <input type="range" id="cgpa-slider-${courseId}" min="${Math.ceil(subjectObtained)}" max="100" value="90" step="1"
                           style="width: 100%; accent-color: var(--primary); margin-bottom: 10px;" 
                           oninput="updateCGPAState('${courseId}', this.value)">
                    <div id="cgpa-req-${courseId}" style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 8px; font-size: 0.8rem;">
                    </div>
                </div>`;
            });
            
            document.getElementById('cgpa-list').innerHTML = html;
            document.getElementById('cgpaModal').style.display = 'flex';
            
            Object.keys(cgpaState).forEach(id => updateCGPAState(id, cgpaState[id].targetPercent, false));
            recalculateTotalCGPA();
        }

        function updateCGPAState(courseId, targetVal, calcTotal=true) {
            targetVal = parseInt(targetVal);
            cgpaState[courseId].targetPercent = targetVal;
            
            let grade = 'C'; let gpa = 5;
            if (targetVal >= 90) { grade = 'O'; gpa = 10; }
            else if (targetVal >= 80) { grade = 'A+'; gpa = 9; }
            else if (targetVal >= 70) { grade = 'A'; gpa = 8; }
            else if (targetVal >= 60) { grade = 'B+'; gpa = 7; }
            else if (targetVal >= 50) { grade = 'B'; gpa = 6; }
            else { grade = 'F'; gpa = 0; }
            
            cgpaState[courseId].gpa = gpa;
            
            document.getElementById(`cgpa-target-label-${courseId}`).innerText = grade + ` (${targetVal}%)`;
            
            let state = cgpaState[courseId];
            let required = targetVal - state.internalObtained;
            let finalMax = 100 - state.internalMax;
            
            let reqDiv = document.getElementById(`cgpa-req-${courseId}`);
            if (required <= 0) {
                reqDiv.innerHTML = `<span style="color:var(--success)">Secured! </span>`;
                reqDiv.style.borderLeft = "4px solid var(--success)";
            } else if (required > finalMax) {
                reqDiv.innerHTML = `<strong style="color:var(--danger)">Mathematically Impossible</strong><br><span style="color:var(--text-sub)">Requires ${required.toFixed(1)} marks over ${finalMax} final marks. Only relative grading can save you.</span>`;
                reqDiv.style.borderLeft = "4px solid var(--danger)";
            } else {
                reqDiv.innerHTML = `Needs <strong style="color:var(--primary)">${required.toFixed(1)}</strong> out of ${finalMax} in final exam.`;
                reqDiv.style.borderLeft = "4px solid var(--primary)";
            }
            
            if(calcTotal) recalculateTotalCGPA();
        }
        
        function recalculateTotalCGPA() {
            let totalPoints = 0;
            let totalCredits = 0;
            Object.values(cgpaState).forEach(s => {
                totalPoints += (s.gpa * s.credits);
                totalCredits += s.credits;
            });
            let est = totalCredits > 0 ? (totalPoints / totalCredits).toFixed(2) : "0.00";
            document.getElementById('cgpa-modal-est').innerText = est;
        }

        function closeCGPACalculator() {
            document.getElementById('cgpaModal').style.display = 'none';
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
            if (estCGPA >= 9.5) percentileHTML = `<div style="margin-top: 15px;"><span style="background: rgba(255,170,0,0.2); color: var(--primary); padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 900; letter-spacing: 1px; display: inline-block;"> TOP 2% OF BATCH</span></div>`;
            else if (estCGPA >= 9.0) percentileHTML = `<div style="margin-top: 15px;"><span style="background: rgba(255,255,255,0.1); color: #fff; padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: 900; letter-spacing: 1px; display: inline-block;"> TOP 10% OF BATCH</span></div>`;

            list.innerHTML = `
                <div class="dashboard-overview image-card fade-in-up" style="padding: 30px 20px; position: relative; overflow: hidden; border-radius: 24px;">
                    <div style="position: absolute; top: 20px; right: 20px; width: 40px; height: 40px; background: rgba(255,255,255,0.1); border-radius: 50%; display: flex; justify-content: center; align-items: center;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
                    </div>
                    <div class="overview-title" style="color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 2px; font-size: 0.8rem; text-align: left; margin-bottom: 5px;">Academic Performance</div>
                    <h1 class="overview-percent" style="color: #fff; text-align: left; font-size: 4rem; margin-bottom: 30px;">${overallPercent}<span style="font-size: 1.5rem;">%</span></h1>
                    <div class="overview-stats" style="background: rgba(0,0,0,0.15); border-radius: 16px; padding: 15px; margin-bottom: 15px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                        <div class="stat-item" style="border: none;">
                            <h4 style="color: #fff; font-size: 1.2rem;">${estCGPA}</h4>
                            <p style="color: rgba(255,255,255,0.7); font-size: 0.7rem; text-transform: uppercase;">Est. CGPA</p>
                        </div>
                        <div class="stat-item" style="border-left: 1px solid rgba(255,255,255,0.1); border-right: 1px solid rgba(255,255,255,0.1);">
                            <h4 style="color: #fff; font-size: 1.2rem;">${grandTotalObtained.toFixed(1)}<span style="font-size: 0.8rem; color: rgba(255,255,255,0.5)">/${grandTotalMax}</span></h4>
                            <p style="color: rgba(255,255,255,0.7); font-size: 0.7rem; text-transform: uppercase;">Score</p>
                        </div>
                        <div class="stat-item" style="border: none;">
                            <h4 style="color: #fff; font-size: 1.2rem;">${grade}</h4>
                            <p style="color: rgba(255,255,255,0.7); font-size: 0.7rem; text-transform: uppercase;">Grade</p>
                        </div>
                    </div>
                    
                    <button class="action-btn" onclick="openCGPACalculator()" style="width: 100%; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; margin-top: 10px; display: flex; justify-content: center; align-items: center; gap: 10px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
                        Open CGPA Calculator
                    </button>
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
                    banner.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg><div><strong> Semester Holidays!</strong><br><small>Enjoy your vacation!</small></div>`;
                    banner.style.display = 'flex';
                } else if (isHoliday) {
                    banner.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><div><strong> Today is a Holiday!</strong><br><small>${plan.title}</small></div>`;
                    banner.style.display = 'flex';
                } else if (todayLocal.getDay() === 0 || todayLocal.getDay() === 6) {
                    banner.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><div><strong> Weekend!</strong><br><small>No classes today.</small></div>`;
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
                grid.innerHTML = `<div class="image-card" style="text-align:center; padding: 20px;"><h4 style="color:var(--accent); margin:0;"> Semester Holidays!</h4><p style="color:var(--text-sub); font-size:0.9rem;">Enjoy your vacation!</p></div>`;
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

            let emojiList = ["", "", ""];

            if (isSemesterVacation(curISOTime)) {
                show = true;
                t = "Semester Holidays! ";
                s = "Enjoy your vacation! Recharge and relax.";
                emojiList = ["", "", "", "", "", ""];
            } else if (plan && plan.title) {
                s = plan.title;
                if (plan.title.includes("Enrolment") || plan.title.includes("Commencement")) {
                    show = true;
                    t = "Welcome Back! ";
                    emojiList = ["", "", "", "", ""];
                } else if (plan.title.includes("Last Working Day")) {
                    show = true;
                    t = "Semester Complete! ";
                    emojiList = ["", "", "", "", ""];
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
                formattedText = formattedText.replace(/\*\*\*(.*?)\*\*\*/g, '<br><span class="special-badge"> $1 </span>');

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
        // ================= PULL TO REFRESH (PREMIUM) =================
        let ptrStartY = 0;
        let ptrActive = false;

        // ================= LONG PRESS CONTEXT MENU =================
        let longPressTimer;
        
        function startLongPress(e, title, type) {
            longPressTimer = setTimeout(() => {
                handleLongPress(e, title, type);
            }, 500);
        }
        
        function cancelLongPress() {
            clearTimeout(longPressTimer);
        }
        
        function handleLongPress(e, title, type) {
            e.preventDefault();
            cancelLongPress();
            
            let clientX = e.clientX || (e.touches && e.touches[0].clientX);
            let clientY = e.clientY || (e.touches && e.touches[0].clientY);
            
            const overlay = document.createElement('div');
            overlay.className = 'context-menu-overlay';
            overlay.onclick = () => overlay.remove();
            
            const menu = document.createElement('div');
            menu.className = 'context-menu';
            menu.style.left = Math.min(clientX, window.innerWidth - 190) + 'px';
            menu.style.top = Math.min(clientY, window.innerHeight - 150) + 'px';
            
            let menuHtml = '';
            if (type === 'attendance') {
                menuHtml = `
                    <button class="context-menu-item" onclick="simulateAttendance('${title.replace(/[^a-zA-Z0-9]/g, '')}', 'attend')">
                        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg> Simulate Attend
                    </button>
                    <button class="context-menu-item" onclick="simulateAttendance('${title.replace(/[^a-zA-Z0-9]/g, '')}', 'bunk')">
                        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11H7v-2h10v2z"/></svg> Simulate Bunk
                    </button>
                    <button class="context-menu-item" onclick="simulateAttendance('${title.replace(/[^a-zA-Z0-9]/g, '')}', 'reset')">
                        <svg viewBox="0 0 24 24"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></svg> Reset Sim
                    </button>
                `;
            } else if (type === 'song') {
                menuHtml = `
                    <button class="context-menu-item" onclick="likeSpotted('${title}', this)">
                        <svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg> Add to Favorites
                    </button>
                    <button class="context-menu-item" onclick="downloadShareImage('${title}', '', '', this)">
                        <svg viewBox="0 0 24 24"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg> Share Snippet
                    </button>
                `;
            }
            
            menu.innerHTML = menuHtml;
            overlay.appendChild(menu);
            document.body.appendChild(overlay);
        }

        // ================= DYNAMIC FAVICON =================
        let faviconCanvas = document.createElement('canvas');
        faviconCanvas.width = 32; faviconCanvas.height = 32;
        let faviconCtx = faviconCanvas.getContext('2d');
        let faviconBars = [5, 15, 25, 10];
        let faviconLastUpdate = 0;
        
        function updateFavicon(isPlaying) {
            const favicon = document.getElementById('dynamic-favicon');
            if (!favicon) return;
            
            if (!isPlaying) {
                favicon.href = 'images/app-icon.svg';
                return;
            }
            
            const now = Date.now();
            if (now - faviconLastUpdate < 150) return; // limit framerate
            faviconLastUpdate = now;
            
            faviconCtx.clearRect(0, 0, 32, 32);
            faviconCtx.fillStyle = '#ffaa00';
            for (let i = 0; i < 4; i++) {
                let h = Math.random() * 20 + 5;
                faviconCtx.fillRect(4 + i*7, 32 - h, 5, h);
            }
            favicon.href = faviconCanvas.toDataURL('image/png');
        }

        function showSyncConfirmation() {
            const modal = document.getElementById('ios-sync-confirm');
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('active'), 10);
        }

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

            if (isLoggedIn) {
                const now = new Date();
                const currentHour = now.getHours();
                let lastMilestone = new Date(now);
                if (currentHour >= 8) {
                    lastMilestone.setHours(8, 0, 0, 0);
                } else {
                    lastMilestone.setHours(0, 0, 0, 0);
                }
                
                const lastAuto = localStorage.getItem('lastAutoSyncTime');
                if (!lastAuto || new Date(parseInt(lastAuto)) < lastMilestone) {
                    if (typeof backgroundSync === 'function') {
                        backgroundSync();
                        localStorage.setItem('lastAutoSyncTime', now.getTime().toString());
                    }
                }
            }
        }
        setInterval(updateLiveHighlighting, 60000);

        function toggleTheme(event) {
            const isLight = document.body.classList.contains('light-mode');
            const x = event ? event.clientX : window.innerWidth / 2;
            const y = event ? event.clientY : window.innerHeight / 2;
            const endRadius = Math.hypot(
                Math.max(x, window.innerWidth - x),
                Math.max(y, window.innerHeight - y)
            );

            if (!document.startViewTransition) {
                document.body.classList.toggle('light-mode');
                localStorage.setItem('srmTheme', !isLight ? 'light' : 'dark');
                return;
            }

            document.documentElement.classList.remove('light-transition');
            if (!isLight) {
                document.documentElement.classList.add('light-transition');
            }

            const transition = document.startViewTransition(() => {
                document.body.classList.toggle('light-mode');
                localStorage.setItem('srmTheme', !isLight ? 'light' : 'dark');
            });

            transition.ready.then(() => {
                const clipPath = [
                    `circle(0px at ${x}px ${y}px)`,
                    `circle(${endRadius}px at ${x}px ${y}px)`
                ];
                document.documentElement.animate(
                    {
                        clipPath: !isLight ? clipPath : [...clipPath].reverse(),
                    },
                    {
                        duration: 600,
                        easing: 'ease-in-out',
                        pseudoElement: !isLight ? '::view-transition-new(root)' : '::view-transition-old(root)',
                    }
                );
            });
        }

        function initApp() {
            try {
                if (localStorage.getItem('srmTheme') === 'light') {
                    document.body.classList.add('light-mode');
                }
                // Invalidate old version profiles to force login
                if (localStorage.getItem('appVersion') !== 'v4') {
                    localStorage.removeItem('squadProfile');
                    localStorage.removeItem('syncRegNo');
                    localStorage.removeItem('syncPwd');
                    localStorage.setItem('appVersion', 'v4');
                }

                const mainContent = document.getElementById('main-content');
                const navBtn = document.getElementById('navButtons');
                const header = document.querySelector('.site-header');
                const appNav = document.querySelector('.app-nav');
                const loginView = document.getElementById('login-view');

                let storedProfile = localStorage.getItem('squadProfile');
                if (storedProfile) {
                    isLoggedIn = true;
                    if (mainContent) { mainContent.style.display = 'block'; mainContent.classList.add('content-visible'); }
                    if (navBtn) navBtn.style.display = 'flex';
                    if (header) header.style.display = 'flex';
                    if (appNav) appNav.style.display = 'flex';
                    if (loginView) loginView.style.display = 'none';

                    try {
                        const profile = JSON.parse(storedProfile);
                        let wn = document.getElementById('welcomeName');
                        if (wn) {
                            const firstName = profile.name ? profile.name.split(' ')[0] : 'User';
                            const hour = new Date().getHours();
                            const day = new Date().getDay();
                            let greeting = "Hi, " + firstName;
                            if (day === 0) greeting = "It's Sunday. No classes. Enjoy your day off, " + firstName + "!";
                            else if (hour >= 5 && hour < 12) greeting = "Good morning, " + firstName + ".";
                            else if (hour >= 12 && hour < 17) greeting = "Good afternoon, " + firstName + ".";
                            else if (hour >= 17 && hour < 21) greeting = "Good evening, " + firstName + ". Time to review?";
                            else greeting = "Late night grind, " + firstName + "?";
                            wn.innerText = greeting;
                        }
                    } catch (e) {
                        console.error("Welcome name error:", e);
                    }
                    
                    // Update Breathing Sync Dot
                    const lastSuccess = localStorage.getItem('lastSyncSuccessTime');
                    const syncDot = document.getElementById('sync-breathing-ring');
                    if (syncDot) {
                        syncDot.className = 'breathing-ring';
                        if (!lastSuccess || (Date.now() - parseInt(lastSuccess) > 24 * 60 * 60 * 1000)) {
                            syncDot.classList.add('stale');
                        } else if (!navigator.onLine) {
                            syncDot.classList.add('offline');
                        }
                    }
                    
                    const logoutBtn = document.getElementById('logoutBtn');
                    if (logoutBtn) logoutBtn.style.display = 'flex';

                    loadSavedData();
                    showTab('dashboard');
                    
                    backgroundSync();
                    
                    const lastSuccessSync = localStorage.getItem('lastSyncSuccessTime');
                    if (!lastSuccessSync || (Date.now() - parseInt(lastSuccessSync) > 12 * 60 * 60 * 1000)) {
                        const banner = document.getElementById('sync-reminder-banner');
                        if (banner) banner.style.display = 'block';
                    }
                } else {
                    isLoggedIn = false;
                    // Hide everything and show login view
                    if (mainContent) mainContent.style.display = 'none';
                    if (navBtn) navBtn.style.display = 'none';
                    if (header) header.style.display = 'none';
                    if (appNav) appNav.style.display = 'none';
                    if (loginView) loginView.style.display = 'flex';
                }

                if (typeof checkAndScheduleNotifications === 'function') {
                    checkAndScheduleNotifications();
                }

                // Global click listener for Install Popup if not running in PWA
                document.body.addEventListener('click', (e) => {
                    if (e.target.closest('#installModal') || e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON' || e.target.closest('.action-btn')) return;
                    if (!window.matchMedia('(display-mode: standalone)').matches) {
                        let m = document.getElementById('installModal');
                        if (m && m.style.display !== 'flex') {
                            m.style.display = 'flex';
                        }
                    }
                });

            } catch (err) {
                console.error("Critical error in initApp:", err);
            }
            
            // Force scroll to top on mobile loads
            setTimeout(() => {
                window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
            }, 50);
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
                triggerLocalNotification("Calendar Reminder ", reminders[todayISOTime]);
                notifiedEvents.custom = true;
            }

            if (timeFloat >= 6.5 && timeFloat < 10 && !notifiedEvents.breakfast) { triggerLocalNotification("Good Morning!  Breakfast:", todaysMenu.Breakfast); notifiedEvents.breakfast = true; }
            if (timeFloat >= 11 && timeFloat < 14 && !notifiedEvents.lunch) { triggerLocalNotification("Lunch Time Approaching! ", todaysMenu.Lunch); notifiedEvents.lunch = true; }
            if (timeFloat >= 15 && timeFloat < 18 && !notifiedEvents.snacks) { triggerLocalNotification("Snack Time! ", todaysMenu.Snacks); notifiedEvents.snacks = true; }
            if (timeFloat >= 18.5 && timeFloat < 21 && !notifiedEvents.dinner) { triggerLocalNotification("Dinner is served! ", todaysMenu.Dinner); notifiedEvents.dinner = true; }
            if (timeFloat >= 22.5 && !notifiedEvents.sleep) { triggerLocalNotification("Time to Sleep! ", "Put the phone away and get some rest for classes tomorrow. "); notifiedEvents.sleep = true; }

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
                            text: 'Flexing my stats!  Hosted on SRM Student Hub.',
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
            list.innerHTML = generateSkeletonCards(5);
            try {
                const res = await fetch(`${BACKEND_URL}/api/leaderboard/${type}`);
                const data = await res.json();
                if (!data || data.length === 0) {
                    list.innerHTML = '<div style="text-align:center; padding: 60px 20px; color: var(--text-sub); font-size: 1.1rem;">No data yet. Be the first to sync! </div>';
                    return;
                }

                // Get current user details from localStorage to highlight them
                const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
                const myRegRaw = profile.regNo || '';
                const myNetId = myRegRaw.split('@')[0].toUpperCase();

                const rankEmojis = ['', '', ''];
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
            list.innerHTML = generateSkeletonCards(3);
            try {
                const res = await fetch(`${BACKEND_URL}/api/projects`);
                const projects = await res.json();
                const staticCards = `
                <div class="image-card fade-in-up" style="transform: none; text-align: left; background: rgba(255,170,0,0.05); border: 1px solid rgba(255,170,0,0.2);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                        <h3 style="color: var(--primary); margin: 0; font-size: 1.3rem; font-family: 'Montserrat', sans-serif;">AI-Powered Medical Diagnosis</h3>
                        <span style="background: rgba(255,170,0,0.2); padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; color: var(--primary); font-weight: bold; white-space: nowrap;"> FEATURED</span>
                    </div>
                    <p style="color: var(--text-sub); line-height: 1.6; font-size: 0.95rem; margin-bottom: 15px;">A full-stack diagnostic tool using quantized LLMs to predict diseases from symptomatic inputs in real-time.</p>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px;">
                        <span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">Next.js</span>
                        <span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">PyTorch</span>
                        <span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">FastAPI</span>
                    </div>
                </div>`;

                const myNetId = getCurrentNetId();

                const dynamicCardsHTML = projects.map(p => {
                    const isOwner = myNetId && p.net_id && myNetId === (p.net_id || '').toLowerCase();
                    const techTags = (p.tech_stack || '').split(',').filter(t => t.trim()).map(t =>
                        `<span style="background: rgba(255,255,255,0.07); padding: 3px 10px; border-radius: 5px; font-size: 0.8rem; color: #aaa;">${t.trim()}</span>`
                    ).join('');
                    const links = [
                        p.github_url ? `<a href="${p.github_url}" target="_blank" style="color: var(--primary); font-weight: bold; font-size: 0.9rem;">GitHub ↗</a>` : '',
                        p.demo_url ? `<a href="${p.demo_url}" target="_blank" style="color: #62d5ff; font-weight: bold; font-size: 0.9rem;">Live Demo →</a>` : ''
                    ].filter(Boolean).join('<span style="color: var(--text-sub); padding: 0 10px;">|</span>');
                    return `
                    <div class="image-card fade-in-up" style="transform: none; text-align: left; position: relative;">
                        ${isOwner ? `<button onclick="deleteProject(${p.id})" style="position: absolute; top: 15px; right: 15px; background: rgba(255,68,68,0.15); border: 1px solid rgba(255,68,68,0.4); color: #ff4444; padding: 5px 12px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.8rem;"> Delete</button>` : ''}
                        <h3 style="color: var(--text-main); margin: 0 0 8px 0; font-size: 1.15rem; font-family: 'Montserrat', sans-serif; padding-right: 80px;">${p.title}</h3>
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

        async function deleteProject(id) {
            if (!confirm("Delete this project?")) return;
            try {
                const res = await fetch(`${BACKEND_URL}/api/projects/delete/${id}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ net_id: getCurrentNetId() })
                });
                const data = await res.json();
                if (data.success) {
                    loadProjects();
                } else {
                    alert("Error: " + (data.error || "Could not delete"));
                }
            } catch (e) {
                alert("Connection error");
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
                        canvas.width = img.width;
                        canvas.height = img.height;
                        
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                        
                        // Compress to 0.8 quality JPEG without changing dimensions
                        const compressedBase64 = canvas.toDataURL('image/jpeg', 0.8);
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
            list.innerHTML = generateSkeletonCards(3);
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
                    
                    ${p.image_url ? `<img src="${p.image_url}" alt="${p.title}" style="width: 100%; height: auto; border-radius: 10px; margin-bottom: 15px; border: 1px solid var(--glass-border);" onerror="this.style.display='none'">` : ''}
                    
                    <p style="color: var(--text-sub); font-size: 0.95rem; margin-bottom: 15px; line-height: 1.5;">${p.description || ''}</p>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--glass-border); padding-top: 15px;">
                        <span style="font-size: 1.2rem; font-weight: 900; color: #62d5ff; font-family: 'Montserrat', sans-serif;">${p.price ? p.price : 'DM for price'}</span>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            ${isOwner ? `<button onclick="deleteMarketItem(${p.id})" style="background: rgba(255,68,68,0.15); border: 1px solid rgba(255,68,68,0.4); color: #ff4444; padding: 8px 14px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 0.85rem;"> Delete</button>` : ''}
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
                    status.style.color = 'var(--success)'; status.innerText = ' Item Posted!';
                    ['market-title','market-desc','market-price','market-phone'].forEach(id => document.getElementById(id).value = '');
                    const label = document.querySelector('label[for="market-image-file"]');
                    if(label) label.innerHTML = ' Click to select a photo from your device (Max 5MB) <input type="file" id="market-image-file" accept="image/*" style="display: none;">';
                    document.getElementById('market-category').selectedIndex = 0;
                    setTimeout(() => { document.getElementById('marketSubmitModal').style.display = 'none'; loadMarketplace(); }, 1500);
                } else {
                    status.style.color = 'var(--danger)'; status.innerText = ' ' + result.error;
                }
            } catch(e) {
                status.style.color = 'var(--danger)'; status.innerText = ' Could not connect to server.';
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
            list.innerHTML = generateSkeletonCards(3);
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
                            <span>Anonymous Fox </span>
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
            list.innerHTML = generateSkeletonCards(3);
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
                                ${isOwner ? `<button onclick="deleteCab(${p.id})" style="background: rgba(255,68,68,0.15); border: 1px solid rgba(255,68,68,0.4); color: #ff4444; padding: 6px 12px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 0.8rem;"> Delete</button>` : ''}
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
                    status.style.color = 'var(--success)'; status.innerText = ' Ride Request Posted!';
                    ['cab-dest','cab-date','cab-time','cab-spots','cab-phone'].forEach(id => document.getElementById(id).value = '');
                    setTimeout(() => { document.getElementById('cabSubmitModal').style.display = 'none'; loadCabs(); }, 1500);
                } else { status.style.color = 'var(--danger)'; status.innerText = ' ' + result.error; }
            } catch(e) { status.style.color = 'var(--danger)'; status.innerText = ' Connection error.'; }
        }

        // ============ EVENTS & CLUB RADAR ============
        async function loadEvents() {
            const list = document.getElementById('events-list');
            if (!list) return;
            list.innerHTML = generateSkeletonCards(3);
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
                            <div style="font-size: 0.95rem; color: var(--primary); margin-bottom: 15px; font-weight: bold;"> ${formattedDate}</div>
                            
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
                    status.style.color = 'var(--success)'; status.innerText = ' Event Posted!';
                    ['event-club','event-title','event-date','event-link'].forEach(id => document.getElementById(id).value = '');
                    const label = document.querySelector('label[for="event-image-file"]');
                    if(label) label.innerHTML = ' Click to upload Event Poster from device <input type="file" id="event-image-file" accept="image/*" style="display: none;">';
                    setTimeout(() => { document.getElementById('eventSubmitModal').style.display = 'none'; loadEvents(); }, 1500);
                } else { status.style.color = 'var(--danger)'; status.innerText = ' ' + result.error; }
            } catch(e) { status.style.color = 'var(--danger)'; status.innerText = ' Connection error.'; }
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
                    status.style.color = 'var(--success)'; status.innerText = ' Project submitted!';
                    ['ph-title','ph-desc','ph-tech','ph-github','ph-demo'].forEach(id => document.getElementById(id).value = '');
                    setTimeout(() => { document.getElementById('projectSubmitModal').style.display = 'none'; loadProjects(); }, 1500);
                } else {
                    status.style.color = 'var(--danger)'; status.innerText = ' ' + result.error;
                }
            } catch(e) {
                status.style.color = 'var(--danger)'; status.innerText = ' Could not connect to server.';
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
            list.innerHTML = generateSkeletonCards(3);
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
                const catIcon = p.category === 'Lost' ? '' : '';

                return `
                <div class="image-card fade-in-up" style="transform: none; text-align: left; position: relative; padding: 20px; border-left: 4px solid ${catColor};">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                        <span style="background: ${catColor}22; color: ${catColor}; padding: 4px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: bold; text-transform: uppercase;">${catIcon} ${p.category || 'Item'}</span>
                        ${isOwner ? `<button onclick="deleteLostFound(${p.id})" style="background: rgba(255,68,68,0.15); border: 1px solid rgba(255,68,68,0.4); color: #ff4444; padding: 5px 12px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.8rem;"> Delete</button>` : ''}
                    </div>
                    
                    <h3 style="color: var(--text-main); margin: 0 0 5px 0; font-size: 1.2rem; font-family: 'Montserrat', sans-serif;">${p.title}</h3>
                    <div style="font-size:0.8rem; color: var(--text-sub); margin-bottom: 10px;">By <b style="color: var(--primary);">${p.poster_name}</b> &bull; ${formatTime}</div>
                    
                    ${p.location ? `<div style="font-size: 0.85rem; color: var(--primary); margin-bottom: 10px;"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 5px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${p.location}</div>` : ''}
                    
                    ${p.image_url ? `<img src="${p.image_url}" alt="${p.title}" style="width: 100%; height: auto; border-radius: 10px; margin-bottom: 12px; border: 1px solid var(--glass-border);" onerror="this.style.display='none'">` : ''}
                    
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
                    status.style.color = 'var(--success)'; status.innerText = ' Item Reported!';
                    ['lf-title','lf-desc','lf-location'].forEach(id => document.getElementById(id).value = '');
                    catEl.selectedIndex = 0;
                    setTimeout(() => { document.getElementById('lfSubmitModal').style.display = 'none'; loadLostFound(); }, 1500);
                } else {
                    status.style.color = 'var(--danger)'; status.innerText = ' ' + result.error;
                }
            } catch(e) {
                status.style.color = 'var(--danger)'; status.innerText = ' Connection error.';
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
                            new Notification('SRM Student Hub ', {
                                body: 'Notifications enabled! You will get updates on exams and deadlines.',
                                icon: '/icon-192.png'
                            });
                        }
                    });
                }
            }, 2000); // Ask after 2 sec so the user sees the app first
        });


        // ============ MUSIC LOUNGE ============
        
        // --- IndexedDB for offline music ---
        function openMusicDB() {
            return new Promise((resolve, reject) => {
                const req = indexedDB.open('srmMusicDB', 1);
                req.onupgradeneeded = (e) => {
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains('downloads')) {
                        db.createObjectStore('downloads', { keyPath: 'id' });
                    }
                };
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
            });
        }
        
        async function saveTrackOffline(track, audioData) {
            const db = await openMusicDB();
            return new Promise((resolve, reject) => {
                const tx = db.transaction('downloads', 'readwrite');
                tx.objectStore('downloads').put({
                    id: track.id,
                    title: track.title,
                    artist: track.artist,
                    cover_data: track.cover_data || '',
                    audio_data: audioData,
                    downloaded_at: Date.now()
                });
                tx.oncomplete = () => resolve();
                tx.onerror = () => reject(tx.error);
            });
        }
        
        async function getOfflineTrack(trackId) {
            try {
                const db = await openMusicDB();
                return new Promise((resolve, reject) => {
                    const tx = db.transaction('downloads', 'readonly');
                    const req = tx.objectStore('downloads').get(trackId);
                    req.onsuccess = () => resolve(req.result || null);
                    req.onerror = () => resolve(null);
                });
            } catch(e) { return null; }
        }
        
        async function getAllOfflineTracks() {
            try {
                const db = await openMusicDB();
                return new Promise((resolve, reject) => {
                    const tx = db.transaction('downloads', 'readonly');
                    const req = tx.objectStore('downloads').getAll();
                    req.onsuccess = () => resolve(req.result || []);
                    req.onerror = () => resolve([]);
                });
            } catch(e) { return []; }
        }
        
        async function deleteOfflineTrack(trackId) {
            const db = await openMusicDB();
            return new Promise((resolve, reject) => {
                const tx = db.transaction('downloads', 'readwrite');
                tx.objectStore('downloads').delete(trackId);
                tx.oncomplete = () => resolve();
                tx.onerror = () => reject(tx.error);
            });
        }
        
        async function isTrackDownloaded(trackId) {
            const track = await getOfflineTrack(trackId);
            return !!track;
        }
        
        async function updateDownloadBtnState(trackId) {
            const btn = document.getElementById('fs-download-btn');
            if (!btn) return;
            const downloaded = await isTrackDownloaded(Number(trackId));
            if (downloaded) {
                btn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="#1DB954"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';
                btn.title = 'Saved to App';
            } else {
                btn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>';
                btn.title = 'Save Offline';
            }
        }
        
        async function loadDownloadsList() {
            const container = document.getElementById('downloads-list');
            if (!container) return;
            const tracks = await getAllOfflineTracks();
            if (tracks.length === 0) {
                container.innerHTML = '<div style="text-align:center; color:var(--text-sub); padding:40px;">No downloaded songs yet.<br>Download songs from the player to listen offline.</div>';
                return;
            }
            let html = '';
            tracks.sort((a, b) => (b.downloaded_at || 0) - (a.downloaded_at || 0));
            tracks.forEach((t, i) => {
                html += `
                <div class="music-track-card fade-in-up" data-id="${t.id}" style="display:flex; align-items:center; gap:14px; padding:14px 18px; background:rgba(255,255,255,0.05); border-radius:14px; margin-bottom:10px; cursor:grab; border:1px solid rgba(255,255,255,0.06); transition:all 0.2s;" onclick="playOfflineTrack('${t.id}')" onmouseover="this.style.background='rgba(255,255,255,0.1)'" onmouseout="this.style.background='rgba(255,255,255,0.05)'">
                    <div style="color: rgba(255,255,255,0.2); margin-right: 5px; font-size: 1.2rem;">⋮⋮</div>
                    <img src="${t.cover_data || 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PC9zdmc+'}" style="width:50px; height:50px; border-radius:10px; object-fit:cover; flex-shrink:0;">
                    <div style="flex:1; min-width:0;">
                        <div style="color:#fff; font-weight:600; font-size:0.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${t.title}</div>
                        <div style="color:var(--text-sub); font-size:0.8rem;">${t.artist}</div>
                    </div>
                    <span style="color:var(--success); font-size:0.7rem; background:rgba(0,204,102,0.15); padding:3px 8px; border-radius:6px; margin-right:10px;">Offline</span>
                    <button class="music-play-btn" style="background:linear-gradient(135deg, #1DB954, #12823b); color:#fff; border:none; border-radius:50%; width:35px; height:35px; display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0;">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                    </button>
                </div>`;
            });
            container.innerHTML = html;
            
            if (window.dlSortable) { window.dlSortable.destroy(); }
            window.dlSortable = Sortable.create(container, {
                animation: 250, delay: 200, delayOnTouchOnly: true, ghostClass: 'sortable-ghost',
                onEnd: function(evt) {
                    if (currentPlaylist.length > 0 && currentPlaylist[0].downloaded_at) {
                        const item = currentPlaylist.splice(evt.oldIndex, 1)[0];
                        currentPlaylist.splice(evt.newIndex, 0, item);
                        if (currentTrackIndex === evt.oldIndex) currentTrackIndex = evt.newIndex;
                        else if (currentTrackIndex > evt.oldIndex && currentTrackIndex <= evt.newIndex) currentTrackIndex--;
                        else if (currentTrackIndex < evt.oldIndex && currentTrackIndex >= evt.newIndex) currentTrackIndex++;
                    }
                }
            });
        }
        
        async function playOfflineTrack(trackId) {
            trackId = Number(trackId);
            const tracks = await getAllOfflineTracks();
            const track = tracks.find(t => t.id === trackId);
            if (!track || !track.audio_data) return alert('Track data not found offline.');
            
            currentPlaylist = tracks.sort((a, b) => (b.downloaded_at || 0) - (a.downloaded_at || 0));
            const idx = currentPlaylist.findIndex(t => t.id === trackId);
            
            nextTrackCache = { index: idx, audio_data: track.audio_data };
            playMusicTrack(idx);
        }
        
        async function removeOfflineTrack(trackId) {
            await deleteOfflineTrack(trackId);
            loadDownloadsList();
        }
        
        function switchMusicTab(tab) {
            const allSection = document.getElementById('music-all-section');
            const dlSection = document.getElementById('music-downloads-section');
            const tabAll = document.getElementById('music-tab-all');
            const tabDl = document.getElementById('music-tab-downloads');
            if (tab === 'downloads') {
                allSection.style.display = 'none';
                dlSection.style.display = 'block';
                tabAll.style.background = 'transparent';
                tabAll.style.color = 'var(--text-sub)';
                tabDl.style.background = 'linear-gradient(135deg,#1DB954,#12823b)';
                tabDl.style.color = '#fff';
                loadDownloadsList();
            } else {
                allSection.style.display = 'block';
                dlSection.style.display = 'none';
                tabDl.style.background = 'transparent';
                tabDl.style.color = 'var(--text-sub)';
                tabAll.style.background = 'linear-gradient(135deg,#1DB954,#12823b)';
                tabAll.style.color = '#fff';
            }
        }

        let currentPlaylist = [];
        let currentTrackIndex = -1;
        let isPlaying = false;
        let playRequestId = 0;
        
        async function loadMusicList() {
            const list = document.getElementById('music-list');
            if(!list) return;
            list.innerHTML = generateSkeletonCards(3);
            try {
                const res = await fetch(`${BACKEND_URL}/api/music`);
                currentPlaylist = await res.json();
                
                if (currentPlaylist.length === 0) {
                    list.innerHTML = `<div style="text-align: center; color: var(--text-sub); padding: 40px;">No tracks found. Upload the first one!</div>`;
                    return;
                }
                
                const myNetId = getCurrentNetId();
                list.innerHTML = currentPlaylist.map((p, index) => {
                    const isOwner = myNetId && p.net_id && myNetId === (p.net_id || '').toLowerCase();
                    const cover = p.cover_data || 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PC9zdmc+';
                    return `
                    <div class="music-card fade-in-up" data-id="${p.id}" onclick="playMusicTrack(${index})" style="transform: none; cursor: grab;">
                        <div style="color: rgba(255,255,255,0.2); margin-right: 10px; font-size: 1.2rem;">⋮⋮</div>
                        <img src="${cover}" class="music-cover" alt="${p.title}">
                        <div class="music-info">
                            <h4 class="music-title">${p.title}</h4>
                            <p class="music-artist">${p.artist}</p>
                            ${p.uploaded_by ? `<div style="font-size:0.7rem; color: rgba(255,255,255,0.4); margin-top: 5px;">Uploaded by ${p.uploaded_by}</div>` : ''}
                        </div>

                        <button class="music-play-btn"><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>
                    </div>`;
                }).join('');
                
                if (window.musicSortable) {
                    window.musicSortable.destroy();
                }
                window.musicSortable = Sortable.create(list, {
                    animation: 250,
                    delay: 200,
                    delayOnTouchOnly: true,
                    ghostClass: 'sortable-ghost',
                    onEnd: async function (evt) {
                        const newOrder = Array.from(list.children).map(child => parseInt(child.getAttribute('data-id')));
                        try {
                            await fetch(`${BACKEND_URL}/api/music/reorder`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ order: newOrder })
                            });
                            // Re-sync array without full reload to keep UI fast
                            const oldPlaylist = [...currentPlaylist];
                            currentPlaylist = newOrder.map(id => oldPlaylist.find(t => t.id === id)).filter(Boolean);
                        } catch(e) { console.error(e); }
                    }
                });
                
                const lastId = localStorage.getItem('lastPlayedTrackId');
                if (lastId && !isPlaying && currentTrackIndex === -1) {
                    const idx = currentPlaylist.findIndex(t => t.id == lastId);
                    if (idx !== -1) {
                        currentTrackIndex = idx;
                        const track = currentPlaylist[idx];
                        document.getElementById('player-title').innerText = track.title;
                        document.getElementById('player-artist').innerText = track.artist;
                        document.getElementById('player-cover').src = track.cover_data || 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PC9zdmc+';
                        document.getElementById('music-player-bar').classList.add('active');
                        fetch(`${BACKEND_URL}/api/music/audio/${track.id}`).then(r=>r.json()).then(d=>{
                            if(d.audio_data) document.getElementById('music-audio-element').src = d.audio_data;
                        });
                    }
                }
            } catch (e) {
                list.innerHTML = '<div style="text-align:center; color: var(--danger); padding: 40px;">Could not load music.</div>';
            }
        }
        
        // ====== ONBOARDING WALKTHROUGH JS ======
        let onboardingCurrentSlide = 0;
        const onboardingTotalSlides = 6;

        function showOnboardingIfNeeded() {
            const hasProfile = localStorage.getItem('squadProfile');
            if (!hasProfile) {
                const overlay = document.getElementById('onboarding-overlay');
                if (overlay) {
                    overlay.style.display = 'flex';
                    // Reset to first slide
                    onboardingCurrentSlide = 0;
                    document.querySelectorAll('.onboarding-slide').forEach((s, i) => {
                        s.classList.remove('active', 'exiting-left', 'entering-right');
                        if (i === 0) s.classList.add('active');
                    });
                    document.querySelectorAll('.onboarding-dot').forEach((d, i) => {
                        d.classList.toggle('active', i === 0);
                    });
                    const nextBtn = document.getElementById('onboarding-next-btn');
                    if (nextBtn) nextBtn.innerText = 'Next';
                }
            }
        }

        function goToOnboardingSlide(idx) {
            if (idx < 0 || idx >= onboardingTotalSlides || idx === onboardingCurrentSlide) return;
            const slides = document.querySelectorAll('.onboarding-slide');
            const dots = document.querySelectorAll('.onboarding-dot');

            // Exit current slide
            slides[onboardingCurrentSlide].classList.remove('active');
            slides[onboardingCurrentSlide].classList.add(idx > onboardingCurrentSlide ? 'exiting-left' : 'entering-right');

            // Enter new slide
            slides[idx].classList.remove('exiting-left', 'entering-right');
            // Force reflow for proper animation
            void slides[idx].offsetWidth;
            slides[idx].classList.add('active');

            // Clean up old slide after transition
            const oldSlide = onboardingCurrentSlide;
            setTimeout(() => {
                slides[oldSlide].classList.remove('exiting-left', 'entering-right');
            }, 500);

            // Update dots
            dots.forEach((d, i) => {
                d.classList.toggle('active', i === idx);
            });

            onboardingCurrentSlide = idx;

            // Update button text
            const nextBtn = document.getElementById('onboarding-next-btn');
            if (idx === onboardingTotalSlides - 1) {
                nextBtn.innerText = 'Get Started';
            } else {
                nextBtn.innerText = 'Next';
            }
        }

        function nextOnboardingSlide() {
            if (onboardingCurrentSlide >= onboardingTotalSlides - 1) {
                finishOnboarding();
            } else {
                goToOnboardingSlide(onboardingCurrentSlide + 1);
            }
        }

        function finishOnboarding() {

            const overlay = document.getElementById('onboarding-overlay');
            if (overlay) {
                overlay.classList.add('closing');
                setTimeout(() => {
                    overlay.style.display = 'none';
                    overlay.classList.remove('closing');
                }, 600);
            }
        }

        // Swipe support for onboarding
        (function() {
            let touchStartX = 0;
            let touchEndX = 0;
            document.addEventListener('DOMContentLoaded', () => {
                const slidesContainer = document.getElementById('onboarding-slides');
                if (!slidesContainer) return;

                slidesContainer.addEventListener('touchstart', e => {
                    touchStartX = e.changedTouches[0].screenX;
                }, {passive: true});

                slidesContainer.addEventListener('touchend', e => {
                    touchEndX = e.changedTouches[0].screenX;
                    const diff = touchStartX - touchEndX;
                    if (Math.abs(diff) > 50) {
                        if (diff > 0) {
                            // Swiped left = next
                            if (onboardingCurrentSlide < onboardingTotalSlides - 1) {
                                goToOnboardingSlide(onboardingCurrentSlide + 1);
                            }
                        } else {
                            // Swiped right = previous
                            if (onboardingCurrentSlide > 0) {
                                goToOnboardingSlide(onboardingCurrentSlide - 1);
                            }
                        }
                    }
                }, {passive: true});

                // Show onboarding
                showOnboardingIfNeeded();
            });
        })();

        // ====== SKELETON LOADING HELPERS ======
        function generateSkeletonCards(count) {
            let html = '';
            for (let i = 0; i < count; i++) {
                html += `
                <div class="skeleton-card" style="animation-delay: ${i * 0.1}s;">
                    <div class="skeleton-row" style="margin-bottom: 14px;">
                        <div class="skeleton skeleton-circle"></div>
                        <div style="flex:1;">
                            <div class="skeleton skeleton-line medium"></div>
                            <div class="skeleton skeleton-line short"></div>
                        </div>
                    </div>
                    <div class="skeleton skeleton-line long"></div>
                    <div class="skeleton skeleton-line full" style="height: 8px; margin-bottom: 0;"></div>
                </div>`;
            }
            return html;
        }

        function generateSkeletonTable() {
            let html = '<div class="skeleton-card" style="padding: 16px;">';
            for (let r = 0; r < 5; r++) {
                html += `<div class="skeleton-row" style="margin-bottom:12px; gap:10px;">`;
                for (let c = 0; c < 4; c++) {
                    html += `<div class="skeleton skeleton-line" style="flex:1; height:16px; margin:0;"></div>`;
                }
                html += `</div>`;
            }
            html += '</div>';
            return html;
        }

        let isRepeat = false;
        let isShuffle = false;
        let nextTrackCache = { index: -1, audio_data: null };

        document.addEventListener("DOMContentLoaded", () => {
            const fsCover = document.getElementById('fs-cover');
            if (fsCover) {
                fsCover.addEventListener('load', function() {
                    extractAlbumColors(this);
                });
            }
        });

        async function preloadNextMusicTrack(index) {
            if (index < 0 || index >= currentPlaylist.length) return;
            const track = currentPlaylist[index];
            try {
                const res = await fetch(`${BACKEND_URL}/api/music/audio/${track.id}`);
                const data = await res.json();
                if (data.audio_data) {
                    nextTrackCache = { index: index, audio_data: data.audio_data };
                }
            } catch(e) {}
        }
        
        async function playMusicTrack(index) {
            if (index < 0 || index >= currentPlaylist.length) return;
            currentTrackIndex = index;
            const track = currentPlaylist[index];
            playRequestId++;
            const currentReqId = playRequestId;
            
            const audioEl = document.getElementById('music-audio-element');
            
            document.getElementById('music-player-bar').classList.add('active');
            document.getElementById('player-title').innerText = track.title;
            document.getElementById('player-artist').innerText = track.artist;
            document.getElementById('player-cover').src = track.cover_data || 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PC9zdmc+';
            const coverSrc = track.cover_data || 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PC9zdmc+';
            document.getElementById('fs-bg-blur').src = coverSrc;
            
            if (document.getElementById('music-fullscreen').style.display === 'flex') {
                document.getElementById('fs-title').innerText = track.title;
                document.getElementById('fs-artist').innerText = track.artist;
                document.getElementById('fs-cover').src = coverSrc;
            } else {
                document.getElementById('fs-cover').src = coverSrc;
            }
            
            // Auto refresh lyrics if open
            const sheet = document.getElementById('fs-lyrics-container');
            const content = document.getElementById('fs-lyrics-content');
            if (sheet && sheet.classList.contains('active')) {
                content.innerText = "Loading lyrics...";
                try {
                    const res = await fetch(`${BACKEND_URL}/api/music/lyrics?artist=${encodeURIComponent(track.artist)}&title=${encodeURIComponent(track.title)}`);
                    const data = await res.json();
                    if (data.success && data.lyrics) {
                        renderLyrics(data, content);
                    } else {
                        content.innerText = "Lyrics not found for this track.\n(Instrumental or unreleased?)";
                    }
                } catch (e) {
                    content.innerText = "Failed to load lyrics.";
                }
            }

            const playAudioData = async (audioData) => {
                // Stop current audio before loading new source
                audioEl.pause();
                
                audioEl.src = audioData;
                
                try {
                    await audioEl.play();
                    isPlaying = true;
                    updatePlayPauseBtn();
                    
                    // Set MediaSession metadata AFTER playback starts to ensure OS registers the active audio session
                    if ('mediaSession' in navigator) {
                        navigator.mediaSession.metadata = new MediaMetadata({
                            title: track.title,
                            artist: track.artist,
                            album: 'SRM Student Hub',
                            artwork: [ { src: track.cover_data || 'https://via.placeholder.com/512', sizes: '512x512', type: 'image/png' } ]
                        });
                        navigator.mediaSession.setActionHandler('play', toggleMusicPlay);
                        navigator.mediaSession.setActionHandler('pause', toggleMusicPlay);
                        navigator.mediaSession.setActionHandler('previoustrack', prevMusicTrack);
                        navigator.mediaSession.setActionHandler('nexttrack', nextMusicTrack);
                    }

                } catch(e) {
                    console.error("Playback prevented:", e);
                    // Auto-skip to next track on playback failure
                    setTimeout(() => { nextMusicTrack(); }, 500);
                    return;
                }
                localStorage.setItem('lastPlayedTrackId', track.id);
                
                // Preload the next track so it can play synchronously in the background later
                let nextIdx = index + 1;
                if (nextIdx >= currentPlaylist.length && currentPlaylist.length > 0) nextIdx = 0;
                if (nextIdx !== index) preloadNextMusicTrack(nextIdx);
            };

            // If we have it cached, play IMMEDIATELY (synchronously) to bypass mobile background restrictions
            if (nextTrackCache.index === index && nextTrackCache.audio_data) {
                playAudioData(nextTrackCache.audio_data);
                return;
            }

            // Otherwise, fetch it (this might fail in background if user gesture expires)
            audioEl.pause();
            audioEl.removeAttribute('src');
            isPlaying = false;
            document.getElementById('player-play-btn').innerHTML = '<div class="css-loader" style="width:15px;height:15px;border-width:2px;border-top-color:#000;"></div>';
            if(document.getElementById('mobile-play-btn')) document.getElementById('mobile-play-btn').innerHTML = '<div class="css-loader" style="width:15px;height:15px;border-width:2px;border-top-color:#fff;"></div>';
            document.getElementById('fs-play-btn').innerHTML = '<div class="css-loader" style="width:20px;height:20px;border-width:2px;border-top-color:#000;"></div>';
            
            try {
                // Try offline/IndexedDB first
                let audioData = null;
                try {
                    const offlineTrack = await getOfflineTrack(track.id);
                    if (offlineTrack && offlineTrack.audio_data) {
                        audioData = offlineTrack.audio_data;
                    }
                } catch(e) {}
                
                if (!audioData) {
                    const res = await fetch(`${BACKEND_URL}/api/music/audio/${track.id}`);
                    const data = await res.json();
                    if (currentReqId !== playRequestId) return;
                    audioData = data.audio_data;
                }
                
                if (audioData) {
                    playAudioData(audioData);
                } else {
                    console.warn("Audio not found, skipping to next...");
                    updatePlayPauseBtn();
                    setTimeout(() => { nextMusicTrack(); }, 500);
                }
            } catch(e) {
                console.warn("Error loading audio, skipping to next...", e);
                updatePlayPauseBtn();
                setTimeout(() => { nextMusicTrack(); }, 500);
            }
        }
        
        function toggleMusicPlay() {
            const audioEl = document.getElementById('music-audio-element');
            if (!audioEl.src) return;
            if (isPlaying) { audioEl.pause(); } else { audioEl.play(); }
            isPlaying = !isPlaying;
            updatePlayPauseBtn();
        }
        
        function changeVolume(val) {
            const audioEl = document.getElementById('music-audio-element');
            if (audioEl) audioEl.volume = val;
        }
        
        function updatePlayPauseBtn() {
            const btns = [
                { el: document.getElementById('player-play-btn'), w: '24', color: '#000' },
                { el: document.getElementById('fs-play-btn'), w: '36', color: '#000' },
                { el: document.getElementById('mobile-play-btn'), w: '24', color: '#fff' }
            ];
            btns.forEach(b => {
                if(b.el) {
                    if (isPlaying) {
                        b.el.innerHTML = `<svg viewBox="0 0 24 24" width="${b.w}" height="${b.w}" fill="${b.color}"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
                    } else {
                        b.el.innerHTML = `<svg viewBox="0 0 24 24" width="${b.w}" height="${b.w}" fill="${b.color}"><path d="M8 5v14l11-7z"/></svg>`;
                    }
                }
            });
        }
        
        function nextMusicTrack() {
            if (isShuffle && currentPlaylist.length > 1) {
                let randomIndex = currentTrackIndex;
                while (randomIndex === currentTrackIndex) {
                    randomIndex = Math.floor(Math.random() * currentPlaylist.length);
                }
                playMusicTrack(randomIndex);
            } else {
                if (currentTrackIndex < currentPlaylist.length - 1) {
                    playMusicTrack(currentTrackIndex + 1);
                } else if (currentPlaylist.length > 0) {
                    playMusicTrack(0);
                }
            }
        }
        
        function prevMusicTrack() {
            if (isShuffle && currentPlaylist.length > 1) {
                let randomIndex = currentTrackIndex;
                while (randomIndex === currentTrackIndex) {
                    randomIndex = Math.floor(Math.random() * currentPlaylist.length);
                }
                playMusicTrack(randomIndex);
            } else {
                if (currentTrackIndex > 0) {
                    playMusicTrack(currentTrackIndex - 1);
                } else if (currentPlaylist.length > 0) {
                    playMusicTrack(currentPlaylist.length - 1);
                }
            }
        }
        
        function toggleRepeat() {
            isRepeat = !isRepeat;
            document.getElementById('repeat-btn-desktop').style.color = isRepeat ? '#1DB954' : '#fff';
            if (document.getElementById('repeat-btn-fs')) {
                document.getElementById('repeat-btn-fs').style.color = isRepeat ? '#1DB954' : '#fff';
            }
        }

        function toggleShuffle() {
            isShuffle = !isShuffle;
            const shuffleBtn = document.getElementById('shuffle-btn-fs');
            if (shuffleBtn) {
                shuffleBtn.style.color = isShuffle ? '#1DB954' : '#fff';
            }
        }
        
        function handleMusicEnded() {
            if (isRepeat) {
                const audioEl = document.getElementById('music-audio-element');
                audioEl.currentTime = 0;
                audioEl.play().catch(e => { console.error('Repeat play failed:', e); nextMusicTrack(); });
            } else {
                nextMusicTrack();
            }
        }

        function handleMusicError() {
            console.warn('Audio element error, auto-skipping to next track...');
            isPlaying = false;
            updatePlayPauseBtn();
            setTimeout(() => { nextMusicTrack(); }, 500);
        }

        function extractAlbumColors(imgEl) {
            try {
                const canvas = document.createElement('canvas');
                canvas.width = 5;
                canvas.height = 5;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(imgEl, 0, 0, 5, 5);
                const imgData = ctx.getImageData(0, 0, 5, 5).data;
                
                const r1 = imgData[0], g1 = imgData[1], b1 = imgData[2];
                const r2 = imgData[50], g2 = imgData[51], b2 = imgData[52];
                const r3 = imgData[96], g3 = imgData[97], b3 = imgData[98];
                
                const color1 = `rgba(${r1}, ${g1}, ${b1}, 0.95)`;
                const color2 = `rgba(${r2}, ${g2}, ${b2}, 0.85)`;
                const color3 = `rgba(${r3}, ${g3}, ${b3}, 0.75)`;
                
                const fsEl = document.getElementById('music-fullscreen');
                if (fsEl) {
                    fsEl.style.setProperty('--fs-accent-1', color1);
                    fsEl.style.setProperty('--fs-accent-2', color2);
                    fsEl.style.setProperty('--fs-accent-3', color3);
                }
            } catch (e) {
                // Fallback for CORS
                const fsEl = document.getElementById('music-fullscreen');
                if (fsEl) {
                    fsEl.style.setProperty('--fs-accent-1', 'rgba(255, 170, 0, 0.75)');
                    fsEl.style.setProperty('--fs-accent-2', 'rgba(138, 43, 226, 0.65)');
                    fsEl.style.setProperty('--fs-accent-3', 'rgba(0, 255, 200, 0.55)');
                }
            }
        }

        async function shareCurrentTrack() {
            const track = currentPlaylist[currentTrackIndex];
            if (!track) return;
            const text = `Listening to "${track.title}" by ${track.artist} on SRM Student Hub!`;
            
            let filesArray = [];
            if (track.cover_data && track.cover_data.startsWith('data:image')) {
                try {
                    const arr = track.cover_data.split(',');
                    const mime = arr[0].match(/:(.*?);/)[1];
                    const bstr = atob(arr[1]);
                    let n = bstr.length;
                    const u8arr = new Uint8Array(n);
                    while(n--){ u8arr[n] = bstr.charCodeAt(n); }
                    const file = new File([u8arr], "cover.jpg", {type: mime});
                    if (navigator.canShare && navigator.canShare({ files: [file] })) {
                        filesArray = [file];
                    }
                } catch(e){}
            }

            if (navigator.share) {
                navigator.share({
                    title: 'SRM Student Hub - Music',
                    text: text,
                    url: window.location.href,
                    ...(filesArray.length > 0 ? { files: filesArray } : {})
                }).catch(() => {});
            } else {
                navigator.clipboard.writeText(text);
                showNotification("Link copied to clipboard!");
            }
        }

        function togglePlaylistQueue() {
            closeFullscreenPlayer();
            const musicSection = document.getElementById('music-section') || document.querySelector('.music-lounge-container');
            if (musicSection) {
                musicSection.scrollIntoView({ behavior: 'smooth' });
                showNotification("Viewing Music Playlist");
            }
        }

        function showDevices() {
            showNotification("Playback Device: System Audio Output");
        }

        window.syncedLyricsData = [];
        window.currentLyricIndex = -1;
        
        function renderLyrics(data, container) {
            window.syncedLyricsData = [];
            window.currentLyricIndex = -1;
            const lines = data.lyrics.split('\n');
            let html = '';
            
            if (data.isSynced) {
                const timeRegex = /\[(\d{2}):(\d{2})\.(\d{2,3})\]/;
                for (const line of lines) {
                    const match = timeRegex.exec(line);
                    if (match) {
                        const mins = parseInt(match[1]);
                        const secs = parseInt(match[2]);
                        const ms = parseInt(match[3]);
                        const totalSeconds = (mins * 60) + secs + (ms / (match[3].length === 3 ? 1000 : 100));
                        
                        const text = line.replace(timeRegex, '').trim();
                        if (text) {
                            window.syncedLyricsData.push({ time: totalSeconds, text: text });
                            const idx = window.syncedLyricsData.length - 1;
                            html += `<div class="apple-lyric-line synced-line" id="lyric-line-${idx}">${text}</div>`;
                        }
                    } else if (line.trim() !== '') {
                         html += `<div class="apple-lyric-line">${line.trim()}</div>`;
                    }
                }
            } else {
                for (const line of lines) {
                    if (line.trim() === '') html += '<br>';
                    else html += `<div class="apple-lyric-line">${line}</div>`;
                }
            }
            container.innerHTML = html;
        }

        async function toggleLyrics() {
            const sheet = document.getElementById('fs-lyrics-container');
            const content = document.getElementById('fs-lyrics-content');
            if (!sheet || !content) return;
            
            if (sheet.classList.contains('active')) {
                sheet.classList.remove('active');
                return;
            }
            
            sheet.classList.add('active');
            content.innerText = "Loading lyrics...";
            
            const track = currentPlaylist[currentTrackIndex];
            if (!track) {
                content.innerText = "No track playing.";
                return;
            }
            
            try {
                const res = await fetch(`${BACKEND_URL}/api/music/lyrics?artist=${encodeURIComponent(track.artist)}&title=${encodeURIComponent(track.title)}`);
                const data = await res.json();
                if (data.success && data.lyrics) {
                    renderLyrics(data, content);
                } else {
                    content.innerText = "Lyrics not found for this track.\n(Instrumental or unreleased?)";
                }
            } catch (e) {
                content.innerText = "Failed to load lyrics.";
            }
        }

        let sleepTimerTimeout = null;
        function toggleSleepTimerMenu() {
            const menu = document.getElementById('sleep-timer-menu');
            menu.style.display = menu.style.display === 'none' ? 'flex' : 'none';
        }
        function setSleepTimer(mins) {
            if (sleepTimerTimeout) clearTimeout(sleepTimerTimeout);
            sleepTimerTimeout = setTimeout(() => {
                const audioEl = document.getElementById('music-audio-element');
                audioEl.pause();
                isPlaying = false;
                updatePlayPauseBtn();
                showNotification("Sleep timer ended");
            }, mins * 60000);
            document.getElementById('sleep-timer-menu').style.display = 'none';
            showNotification(`Sleep timer set for ${mins} minutes`);
        }

        function showNotification(msg) {
            let toast = document.createElement('div');
            toast.innerText = msg;
            toast.style.cssText = `position: fixed; bottom: 100px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.85); color: #fff; padding: 12px 24px; border-radius: 30px; font-size: 0.9rem; z-index: 9999; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); font-family: sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,0.3); pointer-events: none; animation: fadeInOut 3s forwards;`;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        function formatTime(seconds) {
            if (isNaN(seconds)) return "0:00";
            const min = Math.floor(seconds / 60);
            const sec = Math.floor(seconds % 60);
            return `${min}:${sec < 10 ? '0' : ''}${sec}`;
        }
        
        function updateMusicProgress() {
            const audioEl = document.getElementById('music-audio-element');
            const fill = document.getElementById('player-progress-fill');
            const fillFs = document.getElementById('fs-progress-fill');
            const fillMobile = document.getElementById('mobile-progress-fill');
            
            // Dynamic Favicon logic
            const favicon = document.getElementById('dynamic-favicon');
            if (favicon && !audioEl.paused) {
                updateFavicon(true);
            } else if (favicon && audioEl.paused) {
                updateFavicon(false);
            }
            if (audioEl.duration) {
                const perc = `${(audioEl.currentTime / audioEl.duration) * 100}%`;
                if(fill) fill.style.width = perc;
                if(fillFs) fillFs.style.width = perc;
                if(fillMobile) fillMobile.style.width = perc;
                
                if (window.syncedLyricsData && window.syncedLyricsData.length > 0) {
                    const ct = audioEl.currentTime;
                    let activeIndex = -1;
                    
                    for (let i = 0; i < window.syncedLyricsData.length; i++) {
                        if (ct >= window.syncedLyricsData[i].time) {
                            activeIndex = i;
                        } else {
                            break;
                        }
                    }
                    
                    if (activeIndex !== -1 && activeIndex !== window.currentLyricIndex) {
                        const prev = document.getElementById(`lyric-line-${window.currentLyricIndex}`);
                        if (prev) prev.classList.remove('active-lyric');
                        
                        const current = document.getElementById(`lyric-line-${activeIndex}`);
                        if (current) {
                            current.classList.add('active-lyric');
                            const container = document.getElementById('fs-lyrics-container');
                            if (container && container.classList.contains('active')) {
                                current.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            }
                        }
                        window.currentLyricIndex = activeIndex;
                    }
                }
                
                document.getElementById('player-time-current').innerText = formatTime(audioEl.currentTime);
                document.getElementById('player-time-total').innerText = formatTime(audioEl.duration);
                document.getElementById('fs-time-current').innerText = formatTime(audioEl.currentTime);
                document.getElementById('fs-time-total').innerText = formatTime(audioEl.duration);
            }
        }
        
        function seekMusic(e) {
            const audioEl = document.getElementById('music-audio-element');
            if (!audioEl.duration) return;
            const bar = document.getElementById('player-progress-bar');
            audioEl.currentTime = (e.offsetX / bar.clientWidth) * audioEl.duration;
        }
        
        function seekMusicFS(e) {
            const audioEl = document.getElementById('music-audio-element');
            if (!audioEl.duration) return;
            const bar = document.getElementById('fs-progress-bar');
            audioEl.currentTime = (e.offsetX / bar.clientWidth) * audioEl.duration;
        }
        
        function openFullscreenPlayer(e) {
            if(e && e.target.closest('.player-controls') || e && e.target.closest('.progress-container') || e && e.target.closest('.player-right')) return;
            if(!document.getElementById('music-audio-element').src) return;
            
            const track = currentPlaylist[currentTrackIndex];
            document.getElementById('fs-title').innerText = track.title;
            document.getElementById('fs-artist').innerText = track.artist;
            
            const coverSrc = track.cover_data || 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PC9zdmc+';
            const fsCover = document.getElementById('fs-cover');
            fsCover.src = coverSrc;
            
            // Sync repeat and shuffle buttons style
            if (document.getElementById('repeat-btn-fs')) {
                document.getElementById('repeat-btn-fs').style.color = isRepeat ? '#1DB954' : '#fff';
            }
            const shuffleBtn = document.getElementById('shuffle-btn-fs');
            if (shuffleBtn) {
                shuffleBtn.style.color = isShuffle ? '#1DB954' : '#fff';
            }
            
            // Force extraction immediately if already loaded
            if (fsCover.complete) {
                extractAlbumColors(fsCover);
            }
            
            document.getElementById('music-fullscreen').style.display = 'flex';
        }
        
        function closeFullscreenPlayer() {
            document.getElementById('music-fullscreen').style.display = 'none';
        }
        
        async function submitMusic() {
            const title = document.getElementById('music-title').value.trim();
            const artist = document.getElementById('music-artist').value.trim();
            const audioFile = document.getElementById('music-audio-file')?.files[0];
            const coverFile = document.getElementById('music-cover-file')?.files[0];
            const status = document.getElementById('music-status');
            
            if (!title || !artist || !audioFile) {
                status.innerText = "Title, Artist, and Audio File are required!";
                status.style.color = 'var(--danger)';
                return;
            }
            if (audioFile.size > 8 * 1024 * 1024) {
                status.innerText = "Audio file too large (Max 8MB)";
                status.style.color = 'var(--danger)';
                return;
            }
            status.innerText = "Processing audio... Please wait.";
            status.style.color = 'var(--primary)';
            
            try {
                let coverData = '';
                if (coverFile) { coverData = await compressImage(coverFile); }
                const audioBase64 = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.readAsDataURL(audioFile);
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = e => reject(e);
                });
                status.innerText = "Uploading... This may take a moment.";
                const payload = {
                    title: title, artist: artist, audio_data: audioBase64, cover_data: coverData,
                    uploaded_by: 'Student', net_id: getCurrentNetId()
                };
                const res = await fetch(`${BACKEND_URL}/api/music/submit`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                const data = await res.json();
                if (data.success) {
                    status.innerText = "Successfully uploaded!";
                    status.style.color = '#1DB954';
                    setTimeout(() => {
                        document.getElementById('musicSubmitModal').style.display = 'none';
                        loadMusicList();
                    }, 1500);
                } else {
                    status.innerText = "Error: " + (data.error || "Upload failed");
                    status.style.color = 'var(--danger)';
                }
            } catch (e) {
                status.innerText = "Connection error. File might be too large.";
                status.style.color = 'var(--danger)';
            }
        }
        
        async function deleteMusicTrack(id) {
            if (!confirm("Delete this track?")) return;
            try {
                const res = await fetch(`${BACKEND_URL}/api/music/delete/${id}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ net_id: getCurrentNetId() }) });
                const data = await res.json();
                if (data.success) { loadMusicList(); } 
                else { alert("Error: " + (data.error || "Could not delete")); }
            } catch (e) { alert("Connection error"); }
        }
        
        // --- PREMIUM AUDIO VISUALIZER & OFFLINE ---
        let audioCtx;
        let analyser;
        let dataArray;
        
        function initVisualizer() {
            if (audioCtx) return;
            const audioEl = document.getElementById('music-audio-element');
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioCtx.createAnalyser();
            const source = audioCtx.createMediaElementSource(audioEl);
            source.connect(analyser);
            analyser.connect(audioCtx.destination);
            
            analyser.fftSize = 128;
            const bufferLength = analyser.frequencyBinCount;
            dataArray = new Uint8Array(bufferLength);
            
            const canvas = document.getElementById('visualizer-canvas');
            if(!canvas) return;
            canvas.width = 400;
            canvas.height = 120;
            const ctx = canvas.getContext('2d');
            
            function draw() {
                requestAnimationFrame(draw);
                if (!isPlaying) return;
                analyser.getByteFrequencyData(dataArray);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                const barWidth = (canvas.width / bufferLength) * 2.5;
                let x = 0;
                for(let i = 0; i < bufferLength; i++) {
                    const barHeight = dataArray[i] / 2;
                    ctx.fillStyle = `rgb(${barHeight + 100}, 185, 84)`;
                    ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
                    x += barWidth + 2;
                }
                
                // Audio visualizer for Fullscreen Orbs (Bass frequency)
                let bassSum = 0;
                for(let i = 0; i < 15; i++) bassSum += dataArray[i];
                const bassAvg = bassSum / 15;
                const scale = 1 + (bassAvg / 255) * 1.5; // Pulses between 1x and 2.5x
                
                const orbs = document.querySelectorAll('.fs-orb');
                orbs.forEach(orb => {
                    orb.style.transform = `scale(${scale})`;
                    orb.style.background = 'var(--music-orb-color, rgba(29, 185, 84, 0.6))';
                });
            }
            draw();
        }
        
        async function downloadCurrentTrack() {
            if (currentTrackIndex < 0) return;
            const track = currentPlaylist[currentTrackIndex];
            const btn = document.getElementById('fs-download-btn');
            if (btn) btn.innerHTML = '<div class="css-loader" style="width:20px;height:20px;border-width:2px;border-top-color:#1DB954;"></div>';
            try {
                // Check if already downloaded
                const existing = await getOfflineTrack(Number(track.id));
                let audioData;
                if (existing && existing.audio_data) {
                    audioData = existing.audio_data;
                } else {
                    const res = await fetch(`${BACKEND_URL}/api/music/audio/${track.id}`);
                    const data = await res.json();
                    audioData = data.audio_data;
                }
                
                if (audioData) {
                    // Save to IndexedDB for offline playback
                    await saveTrackOffline(track, audioData);
                    
                    // Update download button to show checkmark
                    updateDownloadBtnState(track.id);
                    
                    // Refresh downloads section if visible
                    if (document.getElementById('downloads-list')) loadDownloadsList();
                }
            } catch (e) {
                alert("Could not download track.");
                updateDownloadBtnState(track.id);
            }
        }
        
        document.addEventListener('click', () => {
            if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
        }, { once: true });
        
        // Fullscreen Swipe Logic
        let touchstartX = 0;
        let touchendX = 0;
        
        window.addEventListener('load', () => {
            const fsContainer = document.getElementById('music-fullscreen');
            if(fsContainer) {
                fsContainer.addEventListener('touchstart', e => {
                    touchstartX = e.changedTouches[0].screenX;
                });
                fsContainer.addEventListener('touchend', e => {
                    touchendX = e.changedTouches[0].screenX;
                    const cover = document.getElementById('fs-cover');
                    if (touchendX < touchstartX - 50) {
                        cover.classList.add('swipe-left');
                        setTimeout(() => { nextMusicTrack(); cover.classList.remove('swipe-left'); }, 300);
                    }
                    if (touchendX > touchstartX + 50) {
                        cover.classList.add('swipe-right');
                        setTimeout(() => { prevMusicTrack(); cover.classList.remove('swipe-right'); }, 300);
                    }
                });
            }
        });

    

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.chat-ctx-menu') && !e.target.closest('.chat-menu-btn')) {
                document.querySelectorAll('.chat-ctx-menu').forEach(m => m.style.display = 'none');
            }
        });

        // ============ MASSIVE AI FEATURES ============
        async function submitCrush() {
            const ra = document.getElementById('crush-ra').value.trim();
            const status = document.getElementById('crush-status');
            if (!ra) { status.style.color = '#ff4757'; status.innerText = 'Please enter an RA number.'; return; }
            status.style.color = 'var(--text-main)'; status.innerText = 'Encrypting and matching...';
            
            try {
                const res = await fetch(`${BACKEND_URL}/api/crush/submit`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ net_id: getCurrentNetId(), crush_ra: ra })
                });
                const data = await res.json();
                if (data.success) {
                    if (data.match) {
                        status.style.color = '#ff4757'; status.innerText = 'IT\'S A MATCH!  They like you back!';
                        const modalInner = document.getElementById('crush-modal-inner');
                        const emojis = ['', '', '', '', ''];
                        for (let i = 0; i < 30; i++) {
                            let el = document.createElement('div');
                            el.innerText = emojis[Math.floor(Math.random() * emojis.length)];
                            el.style.position = 'absolute';
                            el.style.left = Math.random() * 100 + '%';
                            el.style.top = '-10%';
                            el.style.fontSize = (Math.random() * 1.5 + 1) + 'rem';
                            el.style.opacity = Math.random() * 0.8 + 0.2;
                            el.style.animation = `floatUpConfetti ${Math.random() * 2 + 2}s linear forwards`;
                            el.style.animationDelay = (Math.random() * 1) + 's';
                            el.style.zIndex = 0;
                            modalInner.appendChild(el);
                        }
                    } else {
                        status.style.color = '#00cc66'; status.innerText = 'Crush secretly logged!  We will notify you if they also log you.';
                    }
                } else {
                    status.style.color = '#ff4757'; status.innerText = data.error || 'Failed to submit.';
                }
            } catch(e) {
                status.style.color = '#ff4757'; status.innerText = 'Network error.';
            }
        }

        async function submitPredict() {
            const cgpa = document.getElementById('ai-cgpa').value.trim();
            const skills = document.getElementById('ai-skills').value.trim();
            const projects = document.getElementById('ai-projects').value.trim();
            const status = document.getElementById('predict-status');
            const resDiv = document.getElementById('predict-result');
            
            if (!cgpa || !skills) { status.style.color = 'var(--danger)'; status.innerText = 'CGPA and Skills are required!'; return; }
            status.style.color = 'var(--primary)'; status.innerText = 'AI is analyzing your profile...';
            resDiv.style.display = 'none';
            
            try {
                const res = await fetch(`${BACKEND_URL}/api/ai/predict`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cgpa, skills, projects })
                });
                const data = await res.json();
                if (data.success) {
                    status.innerText = '';
                    resDiv.style.display = 'block';
                    resDiv.innerText = data.reply;
                } else {
                    status.style.color = 'var(--danger)'; status.innerText = data.error || 'Prediction failed.';
                }
            } catch(e) {
                status.style.color = 'var(--danger)'; status.innerText = 'Network error.';
            }
        }

        let aiFileBase64 = null;
        let aiFileMimeType = null;
        let aiFileName = null;
        
        function handleAIFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            aiFileName = file.name;
            aiFileMimeType = file.type;
            const reader = new FileReader();
            reader.onload = (event) => {
                aiFileBase64 = event.target.result;
                document.getElementById('ai-file-preview-text').innerText = "Attached: " + aiFileName;
                document.getElementById('ai-file-preview-container').style.display = 'block';
            };
            reader.readAsDataURL(file);
        }

        function clearAIFile() {
            aiFileBase64 = null;
            aiFileMimeType = null;
            aiFileName = null;
            document.getElementById('ai-file-input').value = '';
            document.getElementById('ai-file-preview-container').style.display = 'none';
        }

        async function submitChat() {
            const inputEl = document.getElementById('chat-input');
            const msg = inputEl.value.trim();
            if(!msg && !aiFileBase64) return;
            inputEl.value = '';
            
            const history = document.getElementById('chat-history');
            const userBubble = document.createElement('div');
            userBubble.style.cssText = 'background: rgba(255,170,0,0.8); padding: 10px 15px; border-radius: 15px; border-bottom-right-radius: 0; align-self: flex-end; max-width: 80%; color: #fff;';
            let userContent = msg;
            if (aiFileName) userContent += `<br><small style="color: rgba(255,255,255,0.7)"> ${aiFileName}</small>`;
            userBubble.innerHTML = userContent;
            history.appendChild(userBubble);
            
            const reqFileB64 = aiFileBase64;
            const reqMimeType = aiFileMimeType;
            clearAIFile();
            
            const loadingBubble = document.createElement('div');
            loadingBubble.style.cssText = 'background: rgba(138,43,226,0.2); padding: 10px 15px; border-radius: 15px; border-bottom-left-radius: 0; align-self: flex-start; max-width: 80%; color: #aaa;';
            loadingBubble.innerText = 'Thinking...';
            history.appendChild(loadingBubble);
            history.scrollTop = history.scrollHeight;
            
            try {
                const attData = localStorage.getItem('squadAttendance') || "[]";
                const ttData = localStorage.getItem('squadTimetable') || "{}";
                const res = await fetch(`${BACKEND_URL}/api/ai/chat`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: msg, attendance: attData, timetable: ttData, file_base64: reqFileB64, mime_type: reqMimeType })
                });
                const data = await res.json();
                history.removeChild(loadingBubble);
                const botBubble = document.createElement('div');
                botBubble.style.cssText = 'background: rgba(138,43,226,0.2); padding: 10px 15px; border-radius: 15px; border-bottom-left-radius: 0; align-self: flex-start; max-width: 80%; color: #fff; white-space: pre-wrap; line-height: 1.5; font-size: 0.95rem;';
                if(data.success) {
                    botBubble.innerHTML = data.reply
                        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
                        .replace(/!\[.*?\]\((.*?)\)/g, '<br><img src="$1" style="max-width: 100%; border-radius: 10px; margin-top: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);"><br>');
                } else {
                    botBubble.innerText = "Error: " + data.error;
                    botBubble.style.color = "#ff4757";
                }
                history.appendChild(botBubble);
                history.scrollTop = history.scrollHeight;
            } catch(e) {
                history.removeChild(loadingBubble);
            }
        }
        function downloadChatPDF() {
            const chatHistory = document.getElementById('chat-history').innerHTML;
            const printWindow = window.open('', '_blank');
            printWindow.document.write(`
                <html><head><title>Hub AI Export</title>
                <style>
                    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background: #fff; color: #000; line-height: 1.6; }
                    h2 { color: #8a2be2; border-bottom: 2px solid #8a2be2; padding-bottom: 10px; }
                    div[style*="background: rgba(138,43,226,0.2)"] { background: #f4ebff !important; color: #000 !important; margin-bottom: 15px; padding: 15px; border-radius: 10px; border-left: 5px solid #8a2be2; }
                    div[style*="background: rgba(255,170,0,0.8)"] { background: #fff3e0 !important; color: #000 !important; margin-bottom: 15px; padding: 15px; border-radius: 10px; border-left: 5px solid #ffaa00; text-align: right; }
                    img { max-width: 100%; height: auto; border-radius: 8px; margin-top: 10px; border: 1px solid #ccc; }
                </style>
                </head><body>
                <h2>SRM Hub AI Export</h2>
                ${chatHistory}
                <div style="text-align: center; margin-top: 40px; font-size: 0.8rem; color: #888;">Generated by SRM Student Hub AI</div>
                

                    window.onload = function() {
                        setTimeout(() => { window.print(); window.close(); }, 500);
                    };
                <\/script>
                </body></html>
            `);
            printWindow.document.close();
        }

        // ============ VOICE AI ============
        let aiRecognition = null;
        let isVoiceAIListening = false;
        
        function toggleVoiceAI() {
            const btn = document.getElementById('ai-voice-btn');
            if (isVoiceAIListening) {
                if (aiRecognition) aiRecognition.stop();
                return;
            }
            
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                alert("Voice recognition is not supported in this browser. Try Chrome or Edge!");
                return;
            }
            
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            aiRecognition = new SpeechRecognition();
            aiRecognition.continuous = false;
            aiRecognition.interimResults = false;
            aiRecognition.lang = 'en-US';
            
            aiRecognition.onstart = function() {
                isVoiceAIListening = true;
                btn.style.background = '#ff4757';
                btn.style.color = '#fff';
                btn.style.border = '1px solid #ff4757';
                btn.style.animation = 'pulse 1s infinite';
                document.getElementById('chat-input').placeholder = "Listening... Speak now!";
            };
            
            aiRecognition.onresult = function(event) {
                const transcript = event.results[0][0].transcript;
                document.getElementById('chat-input').value = transcript;
                submitChat();
            };
            
            aiRecognition.onerror = function(event) {
                console.error("Speech recognition error", event.error);
                resetVoiceBtn();
            };
            
            aiRecognition.onend = function() {
                resetVoiceBtn();
            };
            
            aiRecognition.start();
        }
        
        function resetVoiceBtn() {
            isVoiceAIListening = false;
            const btn = document.getElementById('ai-voice-btn');
            if(btn) {
                btn.style.background = 'rgba(255,170,0,0.2)';
                btn.style.color = '#ffaa00';
                btn.style.border = '1px solid #ffaa00';
                btn.style.animation = 'none';
            }
            const input = document.getElementById('chat-input');
            if(input) input.placeholder = "Ask anything...";
        }
        
        function speakAIResponse(text) {
            if (!window.speechSynthesis) return;
            window.speechSynthesis.cancel();
            const cleanText = text.replace(/[*_#`]/g, '').replace(/!\[.*?\]\(.*?\)/g, 'Generated an image for you.');
            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.rate = 1.05;
            utterance.pitch = 1.1;
            window.speechSynthesis.speak(utterance);
        }

        // ============ HUB LIVE (GEMINI-STYLE) ============
        let liveRecognition = null;
        let isLiveActive = false;
        let isThinkingOrSpeaking = false;
        let liveMediaRecorder = null;
        let liveAudioChunks = [];
        let isLiveRecording = false;

        function startLiveAI() {
            document.getElementById('liveAiModal').style.display = 'flex';
            document.getElementById('chatModal').style.display = 'none';
            isLiveActive = true;
            isThinkingOrSpeaking = false;
            setLiveState('listening');
            document.getElementById('live-transcript').innerText = "";
        }

        async function startLiveRecord(e) {
            if(e) e.preventDefault();
            if(isThinkingOrSpeaking) return;
            try {
                if(window.speechSynthesis) window.speechSynthesis.cancel();
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                liveMediaRecorder = new MediaRecorder(stream);
                liveAudioChunks = [];
                liveMediaRecorder.ondataavailable = event => liveAudioChunks.push(event.data);
                liveMediaRecorder.onstop = () => {
                    const blob = new Blob(liveAudioChunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        sendLiveAudioPrompt(ev.target.result, blob.type);
                    };
                    reader.readAsDataURL(blob);
                    stream.getTracks().forEach(t => t.stop());
                };
                liveMediaRecorder.start();
                isLiveRecording = true;
                setLiveState('hearing');
                document.getElementById('live-transcript').innerText = "Listening... Release orb to send.";
            } catch(err) {
                document.getElementById('live-transcript').innerText = "Mic Error: " + err.message + " (Please allow microphone access)";
            }
        }

        function stopLiveRecord(e) {
            if(e) e.preventDefault();
            if(isLiveRecording && liveMediaRecorder) {
                liveMediaRecorder.stop();
                isLiveRecording = false;
                setLiveState('thinking');
                document.getElementById('live-transcript').innerText = "Sending audio to AI...";
            }
        }

        async function sendLiveAudioPrompt(base64Data, mimeType) {
            isThinkingOrSpeaking = true;
            setLiveState('thinking');
            document.getElementById('live-transcript').innerText = "AI is thinking...";
            try {
                const attData = localStorage.getItem('squadAttendance') || "[]";
                const ttData = localStorage.getItem('squadTimetable') || "{}";
                const res = await fetch(`${BACKEND_URL}/api/ai/chat`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: "The user sent an audio message. Respond briefly to it as if in a live voice conversation. Maximum 2-3 sentences. No markdown.", attendance: attData, timetable: ttData, file_base64: base64Data, mime_type: mimeType })
                });
                const data = await res.json();
                
                if(!isLiveActive) return;
                
                if(data.success) {
                    setLiveState('speaking');
                    const cleanText = data.reply.replace(/[*_#`]/g, '').replace(/!\[.*?\]\(.*?\)/g, '');
                    document.getElementById('live-transcript').innerText = "AI: " + cleanText;
                    
                    const utterance = new SpeechSynthesisUtterance(cleanText);
                    utterance.rate = 1.05;
                    utterance.pitch = 1.1;
                    utterance.onend = function() {
                        if(isLiveActive) {
                            isThinkingOrSpeaking = false;
                            setLiveState('listening');
                        }
                    };
                    window.speechSynthesis.speak(utterance);
                } else {
                    document.getElementById('live-transcript').innerText = "Error: " + data.error;
                    isThinkingOrSpeaking = false;
                    setLiveState('listening');
                }
            } catch(err) {
                document.getElementById('live-transcript').innerText = "Network Error.";
                isThinkingOrSpeaking = false;
                setLiveState('listening');
            }
        }

        function stopLiveAI() {
            isLiveActive = false;
            isThinkingOrSpeaking = false;
            isLiveRecording = false;
            if(liveMediaRecorder && liveMediaRecorder.state !== 'inactive') liveMediaRecorder.stop();
            if(window.speechSynthesis) window.speechSynthesis.cancel();
            document.getElementById('liveAiModal').style.display = 'none';
        }

        function interruptLiveAI() {
            isThinkingOrSpeaking = false;
            if(window.speechSynthesis) window.speechSynthesis.cancel();
            setLiveState('listening');
            document.getElementById('live-transcript').innerText = "Interrupted. Hold orb to speak again.";
        }
        
        function setLiveState(state) {
            const orb = document.getElementById('live-orb');
            const txt = document.getElementById('live-status-text');
            const btn = document.getElementById('live-interrupt-btn');
            const manualBtn = document.getElementById('live-manual-btn');
            
            orb.className = '';
            
            if (state === 'listening') {
                orb.classList.add('orb-listening');
                txt.innerText = 'Listening...';
                btn.style.display = 'none';
                if(manualBtn) manualBtn.style.display = 'block';
                if(!document.getElementById('live-transcript').innerText.startsWith("You:")) {
                    document.getElementById('live-transcript').innerText = '';
                }
            } else if (state === 'hearing') {
                orb.classList.add('orb-hearing');
                txt.innerText = 'Hearing...';
                btn.style.display = 'none';
                if(manualBtn) manualBtn.style.display = 'none';
            } else if (state === 'thinking') {
                orb.classList.add('orb-thinking');
                txt.innerText = 'Thinking...';
                btn.style.display = 'none';
                if(manualBtn) manualBtn.style.display = 'none';
            } else if (state === 'speaking') {
                orb.classList.add('orb-speaking');
                txt.innerText = 'Speaking...';
                btn.style.display = 'block';
                if(manualBtn) manualBtn.style.display = 'none';
            }
        }
        
        async function sendLivePrompt(msg) {
            msg = msg.trim();
            if(!msg) return;
            
            isThinkingOrSpeaking = true;
            clearTimeout(silenceTimer);
            try { liveRecognition.stop(); } catch(e){}
            setLiveState('thinking');
            
            try {
                const attData = localStorage.getItem('squadAttendance') || "[]";
                const ttData = localStorage.getItem('squadTimetable') || "{}";
                const res = await fetch(`${BACKEND_URL}/api/ai/chat`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: msg + " (Reply briefly as if in a live voice conversation. Maximum 2-3 sentences. No markdown.)", attendance: attData, timetable: ttData })
                });
                const data = await res.json();
                
                if(!isLiveActive) return;
                
                if(data.success) {
                    setLiveState('speaking');
                    const cleanText = data.reply.replace(/[*_#`]/g, '').replace(/!\[.*?\]\(.*?\)/g, '');
                    document.getElementById('live-transcript').innerText = "AI: " + cleanText;
                    
                    const utterance = new SpeechSynthesisUtterance(cleanText);
                    utterance.rate = 1.05;
                    utterance.pitch = 1.1;
                    utterance.onend = function() {
                        if(isLiveActive) {
                            isThinkingOrSpeaking = false;
                            setLiveState('listening');
                            try { liveRecognition.start(); } catch(e){}
                        }
                    };
                    utterance.onerror = function() {
                        if(isLiveActive) {
                            isThinkingOrSpeaking = false;
                            setLiveState('listening');
                            try { liveRecognition.start(); } catch(e){}
                        }
                    };
                    window.speechSynthesis.speak(utterance);
                } else {
                    isThinkingOrSpeaking = false;
                    setLiveState('listening');
                    document.getElementById('live-transcript').innerText = "Error: " + data.error;
                    setTimeout(() => { if(isLiveActive) { try{ liveRecognition.start(); }catch(e){} } }, 1500);
                }
            } catch(e) {
                isThinkingOrSpeaking = false;
                setLiveState('listening');
                document.getElementById('live-transcript').innerText = "Network Error.";
                setTimeout(() => { if(isLiveActive) { try{ liveRecognition.start(); }catch(e){} } }, 1500);
            }
        }

        // CSS moved up to style block

        /* ================= PREMIUM ANIMATIONS ================= */
        // ================= TIMETABLE PUSH NOTIFICATIONS =================
        let notificationInterval = null;
        function setupTimetableNotifications() {
            if (!("Notification" in window)) return;
            if (Notification.permission === "default") {
                Notification.requestPermission();
            }
            if (notificationInterval) clearInterval(notificationInterval);
            
            notificationInterval = setInterval(() => {
                if (Notification.permission !== "granted") return;
                const ttDict = JSON.parse(localStorage.getItem('squadTimetable') || '{}');
                const now = new Date();
                const currentDayNum = now.getDay() || 7; 
                const classes = ttDict[currentDayNum.toString()] || [];
                
                const nowMins = now.getHours() * 60 + now.getMinutes();
                
                classes.forEach(c => {
                    if (!c.startTime) return;
                    const parts = c.startTime.split(':');
                    if (parts.length < 2) return;
                    const startMins = parseInt(parts[0]) * 60 + parseInt(parts[1]);
                    // Check if class is exactly 10 mins from now
                    if (startMins - nowMins === 10) {
                        const notifiedKey = `notified_${now.toDateString()}_${c.courseCode}`;
                        if (!localStorage.getItem(notifiedKey)) {
                            new Notification("Class in 10 mins! ", {
                                body: `${c.subject} - ${c.roomNo}`,
                                icon: "/images/app-icon.svg"
                            });
                            localStorage.setItem(notifiedKey, "true");
                        }
                    }
                });
            }, 60000);
        }
        
        setTimeout(setupTimetableNotifications, 5000);

        // ================= SPOTTED AT SRM =================
        async function loadSpottedFeed() {
            const feed = document.getElementById('spotted-feed');
            feed.innerHTML = generateSkeletonCards(3);
            try {
                const res = await fetch(`${BACKEND_URL}/api/spotted`);
                const posts = await res.json();
                feed.innerHTML = '';
                if (!posts || posts.length === 0) {
                    feed.innerHTML = '<div style="text-align:center; color:var(--text-sub); padding: 20px;">No one spotted yet. Be the first!</div>';
                    return;
                }
                posts.forEach(p => {
                    const dt = new Date(p.created_at);
                    const timeStr = dt.toLocaleDateString() + ' ' + dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    feed.innerHTML += `
                        <div class="image-card" style="padding: 15px; text-align: left; background: rgba(0,0,0,0.2); border: 1px solid var(--glass-border);">
                            <div style="font-family: 'Montserrat', sans-serif; font-size: 1rem; color: #fff; line-height: 1.4; margin-bottom: 10px;">${p.message}</div>
                            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px; margin-top: 5px;">
                                <div style="font-size: 0.8rem; color: var(--text-sub);">${timeStr}</div>
                                <button onclick="likeSpotted(${p.id}, this)" style="background: transparent; border: none; cursor: pointer; color: #ff4757; font-size: 1.1rem; display: flex; align-items: center; gap: 5px;">
                                     <span>${p.likes}</span>
                                </button>
                            </div>
                        </div>
                    `;
                });
            } catch(e) { feed.innerHTML = '<div style="color:var(--danger);text-align:center;">Failed to load feed.</div>'; }
        }

        async function postSpotted() {
            const input = document.getElementById('spotted-input');
            const msg = input.value.trim();
            if(!msg) return alert('Message cannot be empty!');
            input.value = '';
            try {
                const res = await fetch(`${BACKEND_URL}/api/spotted`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg, net_id: getCurrentNetId() })
                });
                const data = await res.json();
                if(data.success) {
                    loadSpottedFeed();
                } else alert('Failed to post: ' + data.error);
            } catch(e) { alert('Network error'); }
        }

        async function likeSpotted(id, btn) {
            try {
                const res = await fetch(`${BACKEND_URL}/api/spotted/like/${id}`, { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    const span = btn.querySelector('span');
                    span.innerText = parseInt(span.innerText) + 1;
                    btn.style.transform = 'scale(1.2)';
                    setTimeout(() => btn.style.transform = 'scale(1)', 200);
                }
            } catch(e) {}
        }

        // ================= CLASS CHAT =================
        function copyClassChat(msg) {
            navigator.clipboard.writeText(msg).then(() => alert('Message copied!'));
        }
        function openDeleteModal(id, isMe) {
            const modal = document.getElementById('wa-delete-modal');
            const opts = document.getElementById('wa-delete-options');
            let html = '';
            
            if (isMe) {
                html += `<button onclick="deleteClassChat('${id}', 'everyone')" style="width: 100%; padding: 15px; background: rgba(255, 71, 87, 0.1); border: 1px solid rgba(255, 71, 87, 0.3); border-radius: 12px; color: #ff4757; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg> Delete for everyone
                </button>`;
            }
            html += `<button onclick="deleteClassChat('${id}', 'me')" style="width: 100%; padding: 15px; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; color: #fff; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg> Delete for me
            </button>`;
            html += `<button onclick="document.getElementById('wa-delete-modal').classList.remove('active');document.getElementById('wa-delete-modal').style.display='none'" style="width: 100%; padding: 15px; background: transparent; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 12px; color: #ccc; cursor: pointer;">Cancel</button>`;
            
            opts.innerHTML = html;
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('active'), 10);
        }

        function deleteClassChat(id, mode) {
            document.getElementById('wa-delete-modal').classList.remove('active');
            document.getElementById('wa-delete-modal').style.display = 'none';
            fetch(`${BACKEND_URL}/api/chat/delete/${id}`, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ net_id: getCurrentNetId(), mode: mode })
            }).then(() => loadClassChat());
        }
        
        let currentCustomAudio = null;
        let currentAudioWaveInterval = null;
        function toggleCustomAudio(btn, url) {
            const container = btn.parentElement;
            const waves = container.querySelectorAll('.wave-bar');
            
            if (currentCustomAudio && currentCustomAudio.src === url && !currentCustomAudio.paused) {
                currentCustomAudio.pause();
                btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
                clearInterval(currentAudioWaveInterval);
                waves.forEach(w => w.style.height = (Math.random()*15+5)+'px');
                return;
            }
            if (currentCustomAudio) {
                currentCustomAudio.pause();
                clearInterval(currentAudioWaveInterval);
                document.querySelectorAll('.custom-audio-player button').forEach(b => b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>');
            }
            
            currentCustomAudio = new Audio(url);
            currentCustomAudio.play();
            btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
            
            currentAudioWaveInterval = setInterval(() => {
                waves.forEach(w => w.style.height = (Math.random()*20+5)+'px');
            }, 100);
            
            currentCustomAudio.onended = () => {
                btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
                clearInterval(currentAudioWaveInterval);
                waves.forEach(w => w.style.height = (Math.random()*15+5)+'px');
            };
        }
        function getUserSection() {
            try {
                const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
                if (profile.department) {
                    // E.g., "Computer Science and Engineering(AIML)-(V1 Section)"
                    const match = profile.department.match(/\(([a-zA-Z0-9-]+)\s*Section\)/i);
                    if (match) return match[1].toUpperCase();
                }
                if (profile.batch && profile.batch.trim() !== '') {
                    // Fallback to Timetable Batch if section isn't in department string
                    let b = profile.batch.trim().toUpperCase();
                    if (b.includes('/')) return 'General'; // Avoid lab batches like "1/1"
                    return b;
                }
            } catch(e) {}
            
            let savedSec = localStorage.getItem('userSection');
            if (savedSec) return savedSec;
            
            try {
                const attData = JSON.parse(localStorage.getItem('squadAttendance') || '[]');
                if (!Array.isArray(attData)) return 'General';
                let section = 'General';
                for (const sub of attData) {
                    const title = sub.courseTitle || sub.name || "";
                    const match = title.match(/[\(\[\s_]([A-Z][0-9])[\)\]\s_]/i);
                    if (match) {
                        section = match[1].toUpperCase();
                        break;
                    }
                }
                localStorage.setItem('userSection', section);
                return section;
            } catch(e) {
                return 'General';
            }
        }
        
        function promptUserSection() {
            const current = getUserSection();
            const newSec = prompt("Enter your class section (e.g. V1, M1, C2):", current !== 'General' ? current : '');
            if(newSec && newSec.trim() !== '') {
                localStorage.setItem('userSection', newSec.trim().toUpperCase());
                loadClassChat();
            }
        }

        let chatInterval = null;
        let chatImageBase64 = "";

        function openClassChat() {
            const section = getUserSection();
            document.getElementById('chat-title').innerText = `Class Chat - ${section}`;
            switchView('chat-view');
            
            const history = document.getElementById('class-chat-history');
            if (history.children.length === 0) {
                history.innerHTML = `
                    <div class="chat-skeleton-container" id="chat-loading-skeleton">
                        <div class="chat-skeleton chat-skeleton-left"></div>
                        <div class="chat-skeleton chat-skeleton-right"></div>
                        <div class="chat-skeleton chat-skeleton-left" style="width:40%;"></div>
                        <div class="chat-skeleton chat-skeleton-right" style="width:70%;"></div>
                    </div>
                `;
            }

            loadClassChat();
            if(chatInterval) clearInterval(chatInterval);
            chatInterval = setInterval(loadClassChat, 3000);
        }
        
        async function loadClassChat() {
            if (!document.getElementById('chat-view').classList.contains('active')) {
                if(chatInterval) { clearInterval(chatInterval); chatInterval = null; }
                return;
            }
            const section = getUserSection();
            const myNetId = getCurrentNetId();
            const history = document.getElementById('class-chat-history');
            const wasAtBottom = history.scrollHeight - history.scrollTop <= history.clientHeight + 50;

            try {
                const res = await fetch(`${BACKEND_URL}/api/chat/${section}`);
                const msgs = await res.json();
                
                const noMsg = document.getElementById('no-msg-txt');
                if (noMsg) noMsg.remove();
                const spinner = history.querySelector('div[style*="animation: spin"]');
                if (spinner) spinner.remove();

                if (!msgs || msgs.length === 0) {
                    if (history.children.length === 0) {
                        history.innerHTML = '<div style="text-align:center; color:var(--text-sub); margin-top: auto; margin-bottom: auto;" id="no-msg-txt">No messages yet. Say hi! </div>';
                    }
                    return;
                }

                const currentIds = new Set(msgs.map(m => m.id));
                Array.from(history.children).forEach(child => {
                    if (child.dataset.msgId && !currentIds.has(parseInt(child.dataset.msgId))) {
                        child.remove();
                    }
                });

                msgs.forEach(m => {
                    const isMe = m.sender_net_id === myNetId;
                    const deletedByMe = m.deleted_by && m.deleted_by.includes(myNetId);
                    if (deletedByMe && !m.deleted_for_all) {
                        const ex = document.getElementById('chat-msg-' + m.id);
                        if(ex) ex.remove();
                        return;
                    }

                    let existing = document.getElementById('chat-msg-' + m.id);
                    if (existing) {
                        if (m.deleted_for_all && existing.dataset.deleted !== "true") {
                            existing.dataset.deleted = "true";
                            existing.innerHTML = `<div style="font-style: italic; color: rgba(255,255,255,0.6); display:flex; align-items:center; gap:5px;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg> This message was deleted</div>`;
                        }
                        return;
                    }
                    
                    const dt = new Date(m.created_at);
                    const timeStr = dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    
                    const bubble = document.createElement('div');
                    bubble.id = 'chat-msg-' + m.id;
                    bubble.dataset.msgId = m.id;
                    bubble.className = "chat-bubble-anim fade-in-up";
                    bubble.style.cssText = `max-width: 85%; padding: 12px 16px; border-radius: 18px; display: flex; flex-direction: column; gap: 5px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.2); backdrop-filter: blur(10px); ${isMe ? 'background: linear-gradient(135deg, rgba(0, 204, 102, 0.8), rgba(0, 153, 77, 0.9)); color: white; align-self: flex-end; border-bottom-right-radius: 4px; border: 1px solid rgba(0,255,100,0.3);' : 'background: rgba(255,255,255,0.1); color: white; align-self: flex-start; border-bottom-left-radius: 4px; border: 1px solid rgba(255,255,255,0.1);'}`;
                    
                    if (m.deleted_for_all) {
                        bubble.dataset.deleted = "true";
                        bubble.innerHTML = `<div style="font-style: italic; color: rgba(255,255,255,0.6); display:flex; align-items:center; gap:5px;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg> This message was deleted</div>`;
                    } else {
                        let html = '';
                        html += `<div style="font-size: 0.75rem; font-weight: bold; color: ${isMe ? 'rgba(255,255,255,0.9)' : '#ffaa00'}; margin-bottom: 4px; display:flex; justify-content:space-between; align-items:center;">
                            <span>${isMe ? 'You' : m.sender_name}</span>
                            <span class="chat-menu-btn" style="cursor:pointer; opacity:0.6; padding:0 5px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg></span>
                        </div>`;

                        const safeMsg = m.message ? m.message.replace(/'/g, "\\'").replace(/"/g, '&quot;') : '';
                        const menuHtml = `<div class="chat-ctx-menu" style="display:none; position:absolute; top:25px; right:10px; background:rgba(20,20,20,0.95); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:5px 0; z-index:100; box-shadow:0 10px 25px rgba(0,0,0,0.5); backdrop-filter:blur(15px); flex-direction:column; min-width:120px;">
                            <div class="ctx-item" onclick="copyClassChat('${safeMsg}')" style="padding:10px 15px; cursor:pointer; font-size:0.9rem; transition:background 0.2s;">Copy</div>
                            <div class="ctx-item" onclick="openDeleteModal('${m.id}', ${isMe})" style="padding:10px 15px; cursor:pointer; font-size:0.9rem; color:#ff4757; transition:background 0.2s;">Delete</div>
                        </div>`;
                        html += menuHtml;

                        if (m.image_url) html += `<img src="${m.image_url}" style="max-width: 100%; border-radius: 12px; margin-bottom: 5px; box-shadow: 0 5px 15px rgba(0,0,0,0.3);" onclick="window.open('${m.image_url}')">`;
                        
                        if (m.audio_url) {
                            html += `
                            <div class="custom-audio-player" style="display:flex; align-items:center; gap:10px; background:rgba(0,0,0,0.2); padding:8px 12px; border-radius:30px; margin-bottom:5px;">
                                <button onclick="toggleCustomAudio(this, '${m.audio_url}')" style="background:#fff; color:#000; border:none; border-radius:50%; width:35px; height:35px; display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0;"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>
                                <div class="audio-waves" style="flex:1; display:flex; gap:3px; align-items:center; height:20px;">
                                    ${Array(15).fill(0).map(()=>`<div class="wave-bar" style="width:4px; height:${Math.random()*15+5}px; background:rgba(255,255,255,0.5); border-radius:2px; transition:height 0.2s;"></div>`).join('')}
                                </div>
                            </div>`;
                        }
                        
                        if (m.message) html += `<div style="word-wrap: break-word; line-height: 1.5; font-size: 0.95rem;">${m.message}</div>`;
                        html += `<div style="font-size: 0.65rem; color: rgba(255,255,255,0.7); align-self: flex-end; margin-top: 4px;">${timeStr}</div>`;
                        
                        bubble.innerHTML = html;
                        
                        setTimeout(() => {
                            const menuBtn = bubble.querySelector('.chat-menu-btn');
                            const menu = bubble.querySelector('.chat-ctx-menu');
                            if (menu) {
                                if (menuBtn) {
                                    menuBtn.onclick = (e) => {
                                        e.stopPropagation();
                                        document.querySelectorAll('.chat-ctx-menu').forEach(mx => { if(mx !== menu) mx.style.display='none'; });
                                        menu.style.display = menu.style.display === 'none' ? 'flex' : 'none';
                                    };
                                }
                                // Long Press & Right Click Logic
                                let touchTimer = null;
                                bubble.addEventListener('contextmenu', (e) => {
                                    e.preventDefault();
                                    document.querySelectorAll('.chat-ctx-menu').forEach(mx => mx.style.display='none');
                                    menu.style.display = 'flex';
                                });
                                bubble.addEventListener('touchstart', () => {
                                    touchTimer = setTimeout(() => {
                                        document.querySelectorAll('.chat-ctx-menu').forEach(mx => mx.style.display='none');
                                        menu.style.display = 'flex';
                                        if (navigator.vibrate) navigator.vibrate(50);
                                    }, 500);
                                }, {passive: true});
                                bubble.addEventListener('touchend', () => clearTimeout(touchTimer));
                                bubble.addEventListener('touchmove', () => clearTimeout(touchTimer));
                            }
                        }, 0);
                    }
                    history.appendChild(bubble);
                });
                
                if (wasAtBottom) history.scrollTop = history.scrollHeight;
            } catch(e) {}
        }

        async function sendClassChat() {
            const input = document.getElementById('class-chat-input');
            const msg = input.value.trim();
            if(!msg && !chatImageBase64 && !chatAudioBase64) return;
            
            input.value = '';
            const img = chatImageBase64;
            const audio = chatAudioBase64;
            clearChatImage();
            
            const section = getUserSection();
            const netId = getCurrentNetId();
            let name = 'Anonymous';
            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            if (profile.name) name = profile.name;
            else if (document.getElementById('name') && document.getElementById('name').value) name = document.getElementById('name').value.trim();
            
            // Optimistic UI Append
            const history = document.getElementById('class-chat-history');
            const tempId = 'temp-' + Date.now();
            const timeStr = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            const noMsg = document.getElementById('no-msg-txt');
            if (noMsg) noMsg.remove();
            
            let tempHtml = `<div id="${tempId}" class="chat-bubble-anim fade-in-up" style="max-width: 85%; padding: 12px 16px; border-radius: 18px; display: flex; flex-direction: column; gap: 5px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.2); backdrop-filter: blur(10px); background: linear-gradient(135deg, rgba(0, 204, 102, 0.5), rgba(0, 153, 77, 0.6)); color: white; align-self: flex-end; border-bottom-right-radius: 4px; border: 1px solid rgba(0,255,100,0.3); opacity: 0.8;">
                <div style="font-size: 0.75rem; font-weight: bold; color: rgba(255,255,255,0.9); margin-bottom: 4px;">You (Sending...)</div>`;
            
            if (img) tempHtml += `<img src="${img}" style="max-width: 100%; border-radius: 12px; margin-bottom: 5px; opacity: 0.7;">`;
            if (audio) tempHtml += `<div class="custom-audio-player" style="display:flex; align-items:center; gap:10px; background:rgba(0,0,0,0.2); padding:8px 12px; border-radius:30px; margin-bottom:5px;"><button style="background:#fff; color:#000; border:none; border-radius:50%; width:35px; height:35px; display:flex; align-items:center; justify-content:center; flex-shrink:0;"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button><div style="flex:1;font-size:0.8rem;">Audio (Uploading)</div></div>`;
            if (msg) tempHtml += `<div style="word-wrap: break-word; line-height: 1.5; font-size: 0.95rem;">${msg}</div>`;
            tempHtml += `<div style="font-size: 0.65rem; color: rgba(255,255,255,0.7); align-self: flex-end; margin-top: 4px;">${timeStr}</div></div>`;
            
            history.insertAdjacentHTML('beforeend', tempHtml);
            history.scrollTop = history.scrollHeight;
            chatAudioBase64 = null;
            
            try {
                await fetch(`${BACKEND_URL}/api/chat/${section}`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ sender_name: name, sender_net_id: netId, message: msg, image_url: img, audio_url: audio })
                });
                loadClassChat();
            } catch(e) { 
                alert('Failed to send message'); 
                const el = document.getElementById(tempId);
                if(el) el.remove();
            }
        }

        function handleChatImageUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (event) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let width = img.width, height = img.height;
                    const max_size = 800;
                    if (width > height) { if (width > max_size) { height *= max_size / width; width = max_size; } } 
                    else { if (height > max_size) { width *= max_size / height; height = max_size; } }
                    canvas.width = width; canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);
                    chatImageBase64 = canvas.toDataURL('image/jpeg', 0.6);
                    document.getElementById('chat-image-preview').src = chatImageBase64;
                    document.getElementById('chat-image-preview-container').style.display = 'block';
                };
                img.src = event.result;
            };
            reader.readAsDataURL(file);
        }

        function clearChatImage() {
            chatImageBase64 = '';
            document.getElementById('chat-image-preview-container').style.display = 'none';
            document.getElementById('chat-image-input').value = '';
        }
        
        let chatAudioRecorder = null;
        let chatAudioChunks = [];
        let chatAudioBase64 = null;
        let isChatRecording = false;

        async function startChatAudio(e) {
            if(e) e.preventDefault();
            if(isChatRecording) return;
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                chatAudioRecorder = new MediaRecorder(stream);
                chatAudioChunks = [];
                chatAudioRecorder.ondataavailable = event => { if(event.data.size > 0) chatAudioChunks.push(event.data); };
                chatAudioRecorder.onstop = () => {
                    const blob = new Blob(chatAudioChunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.onloadend = () => { chatAudioBase64 = reader.result; sendClassChat(); };
                    reader.readAsDataURL(blob);
                    stream.getTracks().forEach(track => track.stop());
                };
                chatAudioRecorder.start();
                isChatRecording = true;
                const btn = document.getElementById('chat-record-btn');
                btn.style.background = 'rgba(255, 71, 87, 0.3)';
                btn.style.transform = 'scale(1.2)';
            } catch(err) { alert("Microphone access required: " + err.message); }
        }

        function stopChatAudio(e) {
            if(e) e.preventDefault();
            if(!isChatRecording || !chatAudioRecorder) return;
            chatAudioRecorder.stop();
            isChatRecording = false;
            const btn = document.getElementById('chat-record-btn');
            btn.style.background = 'rgba(0, 204, 102, 0.1)';
            btn.style.transform = 'scale(1)';
        }

        // ================= DYNAMIC ATMOSPHERES =================
        function applyDynamicAtmospheres() {
            const hour = new Date().getHours();
            document.body.classList.remove('theme-sunset', 'theme-night', 'theme-rain');
            if (hour >= 17 && hour < 19) document.body.classList.add('theme-sunset');
            else if (hour >= 19 || hour < 5) document.body.classList.add('theme-night');

            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(async (pos) => {
                    try {
                        const lat = pos.coords.latitude;
                        const lon = pos.coords.longitude;
                        const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=precipitation`);
                        const data = await res.json();
                        if (data && data.current && data.current.precipitation > 0) {
                            document.body.classList.add('theme-rain');
                        }
                    } catch(e) {}
                });
            }
        }
        setTimeout(applyDynamicAtmospheres, 2000);

        // ================= CINEMATIC DAY RECAP (STORY MODE) =================
        let currentStorySlide = 1;
        let storyTimer = null;
        let storyInterval = null;

        function openStoryMode() {
            const profile = JSON.parse(localStorage.getItem('squadProfile') || '{}');
            const summary = JSON.parse(localStorage.getItem('squadSummary') || '{}');
            
            let totalClasses = 0, totalAttended = 0;
            if(summary.totalConducted) totalClasses = parseInt(summary.totalConducted);
            if(summary.totalAttended) totalAttended = parseInt(summary.totalAttended);
            const totalBunked = Math.max(0, totalClasses - totalAttended);
            
            let lowestMargin = 999;
            let lowestSub = 'None';
            const attData = JSON.parse(localStorage.getItem('squadAttendance') || '[]');
            attData.forEach(s => {
                if(s.margin < lowestMargin) { lowestMargin = s.margin; lowestSub = s.title; }
            });

            document.getElementById('story-greeting').innerText = `Hey, ${profile.name ? profile.name.split(' ')[0] : 'Student'}!`;
            document.getElementById('story-stat-1').innerHTML = `You've survived <strong>${totalClasses}</strong> classes so far.<br>You've successfully bunked <strong>${totalBunked}</strong> of them.`;
            
            if (lowestSub !== 'None') {
                document.getElementById('story-stat-2').innerHTML = `Your most dangerous subject is <strong>${lowestSub}</strong>.<br>You have a margin of exactly <strong>${lowestMargin}</strong> bunks left.`;
            } else {
                document.getElementById('story-stat-2').innerHTML = `Your attendance looks fully clean!<br>Keep up the great work.`;
            }
            
            const cgpa = summary.cgpa || 'N/A';
            document.getElementById('story-stat-3').innerHTML = `Your current CGPA stands at <strong>${cgpa}</strong>.<br>Keep pushing forward, you're doing great!`;

            document.getElementById('story-modal').style.display = 'flex';
            setTimeout(() => document.getElementById('story-modal').classList.add('active'), 10);
            
            currentStorySlide = 1;
            showStorySlide(currentStorySlide);
        }

        function closeStoryMode() {
            document.getElementById('story-modal').classList.remove('active');
            setTimeout(() => document.getElementById('story-modal').style.display = 'none', 300);
            clearTimeout(storyTimer);
            clearInterval(storyInterval);
        }

        function showStorySlide(index) {
            clearTimeout(storyTimer);
            clearInterval(storyInterval);
            
            [1,2,3].forEach(i => {
                const slide = document.getElementById(`story-slide-${i}`);
                if(slide) slide.style.display = (i === index) ? 'flex' : 'none';
                const fill = document.getElementById(`story-prog-${i}`);
                if(fill) {
                    if (i < index) fill.style.width = '100%';
                    else if (i > index) fill.style.width = '0%';
                    else fill.style.width = '0%';
                }
            });
            
            let prog = 0;
            const currentFill = document.getElementById(`story-prog-${index}`);
            if(currentFill) {
                storyInterval = setInterval(() => {
                    prog += 2;
                    if(prog <= 100) currentFill.style.width = `${prog}%`;
                }, 100);
            }

            storyTimer = setTimeout(() => {
                advanceStory();
            }, 5000);
        }

        function advanceStory() {
            if (currentStorySlide < 3) {
                currentStorySlide++;
                showStorySlide(currentStorySlide);
            } else {
                closeStoryMode();
            }
        }
    