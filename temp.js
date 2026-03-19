
// ================= GLOBAL STATE =================
const BACKEND_URL = 'https://srm-student-hub-1.onrender.com';
let isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';
let attendanceData = [];
let timetableData = {};
let currentBatch = 1;

// ================= PWA INSTALLATION =================
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (localStorage.getItem('installDismissed') !== 'true') {
        setTimeout(openInstallModal, 2000);
    }
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
    "2026-01-01": { type: "Holiday", title: "New Year's Day - Holiday" },
    "2026-01-05": { type: "Event", title: "Enrollment day - B.Tech" },
    "2026-01-08": { type: "Event", title: "Commencement of Classes" },
    "2026-01-14": { type: "Holiday", title: "Pongal - Holiday" },
    "2026-01-15": { type: "Holiday", title: "Thiruvalluvar Day - Holiday" },
    "2026-01-16": { type: "Holiday", title: "Uzhavar Thirunal - Holiday" },
    "2026-01-26": { type: "Holiday", title: "Republic Day - Holiday" },
    "2026-02-10": { type: "Holiday", title: "Thaipusam - Holiday" },
    "2026-03-04": { type: "Holiday", title: "Holi" },
    "2026-03-19": { type: "Holiday", title: "Telugu New Year's Day - Holiday" },
    "2026-03-21": { type: "Holiday", title: "Ramzan - Holiday" },
    "2026-03-31": { type: "Holiday", title: "Mahaveer Jayanthi - Holiday" },
    "2026-04-03": { type: "Holiday", title: "Good Friday - Holiday" },
    "2026-04-14": { type: "Holiday", title: "Tamil New Year's Day / Dr. B.R. Ambedkar's Birthday - Holiday" },
    "2026-05-01": { type: "Holiday", title: "May Day - Holiday" },
    "2026-05-06": { type: "Event", title: "Last working Day" },
    "2026-05-27": { type: "Holiday", title: "Bakrid - Holiday" },
    "2026-06-26": { type: "Holiday", title: "Muharram - Holiday" }
};

// Auto-generate accurate Day Orders for 2026 Even Semester
const startDate = new Date("2026-01-08");
const endDate = new Date("2026-05-06");
const holidays = ["2026-01-14", "2026-01-15", "2026-01-16", "2026-01-26", "2026-02-10", "2026-03-04", "2026-03-19", "2026-03-31", "2026-04-03", "2026-04-14", "2026-05-01"];

let dOrder = 1;
for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
    // Adjust offset to get local YYYY-MM-DD reliably
    let curISOTime = new Date(d.getTime() - (d.getTimezoneOffset() * 60000)).toISOString().slice(0, 10);

    let dayOfWeek = d.getDay();
    if (dayOfWeek !== 0 && dayOfWeek !== 6 && !holidays.includes(curISOTime)) {
        // If it's a weekday and not a holiday, assign day order
        // Keep any existing events (like Commencement) and just add the Day Order logic
        let existingTitle = srmPlanner[curISOTime] ? srmPlanner[curISOTime].title + ` (Day Order ${dOrder})` : `Regular Day Order ${dOrder}`;
        srmPlanner[curISOTime] = { type: "Day Order", value: dOrder, title: existingTitle };

        dOrder = dOrder === 5 ? 1 : dOrder + 1;
    }
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
}

function loadSavedData() {
    const savedAtt = JSON.parse(localStorage.getItem('squadAttendance') || '[]');
    const savedMarks = JSON.parse(localStorage.getItem('squadMarks') || '[]');
    const savedTT = JSON.parse(localStorage.getItem('squadTimetable') || '{}');

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

async function startLiveSync() {
    const regNo = document.getElementById('srm-reg').value.trim();
    const pwd = document.getElementById('srm-pwd').value;
    const statusText = document.getElementById('sync-status');

    if (!regNo || !pwd) {
        alert("Please enter your NetID/Email and Password.");
        return;
    }

    statusText.innerText = "🔄 Syncing with Academia... This takes up to 90 seconds.";
    statusText.style.color = "var(--primary)";

    try {
        const res = await fetch(`${BACKEND_URL}/api/start_session`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ regNo: regNo, pwd: pwd, batch: currentBatch })
        });

        const result = await res.json();

        if (!result.success) {
            statusText.innerText = "❌ " + result.error;
            statusText.style.color = "var(--danger)";
            return;
        }

        statusText.innerText = "✅ Success! Dashboard Updated.";
        statusText.style.color = "var(--success)";

        isLoggedIn = true;
        localStorage.setItem("isLoggedIn", "true");
        updateHomeState();

        const attList = Array.isArray(result.data) ? result.data : [];
        const marksList = Array.isArray(result.marks) ? result.marks : [];
        const ttDict = result.timetable || {};

        localStorage.setItem('squadAttendance', JSON.stringify(attList));
        localStorage.setItem('squadMarks', JSON.stringify(marksList));
        localStorage.setItem('squadTimetable', JSON.stringify(ttDict));

        try { renderAttendance(attList); } catch (e) { console.error("Attendance Render Error:", e); }
        try { renderMarks(marksList); } catch (e) { console.error("Marks Render Error:", e); }
        try { renderTimetable(ttDict); } catch (e) { console.error("Timetable Render Error:", e); }

        setTimeout(() => closeSyncModal(), 1500);

    } catch (e) {
        statusText.innerText = "❌ Could not connect to backend server.";
        statusText.style.color = "var(--danger)";
    } finally {
        document.getElementById('srm-pwd').value = '';
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

function renderAttendance(attData) {
    const list = document.getElementById('attendance-list');
    if (!list) return;

    list.innerHTML = '';
    let totalAtt = 0;
    let totalClasses = 0;
    attendanceData = attData || [];

    attendanceData.forEach(sub => {
        let attended = parseInt(sub.attended) || 0;
        let total = parseInt(sub.total) || 0;
        let name = sub.courseTitle || sub.name || "Unknown Subject";

        totalAtt += attended;
        totalClasses += total;

        const percentage = total === 0 ? 0 : ((attended / total) * 100).toFixed(1);
        const isGood = percentage >= 75;
        const barColor = isGood ? 'var(--success)' : 'var(--danger)';

        let statusText = isGood
            ? `You can safely bunk ${Math.floor((attended - (0.75 * total)) / 0.75)} classes.`
            : `Attend ${Math.ceil(((0.75 * total) - attended) / 0.25)} more classes to hit 75%.`;

        list.innerHTML += `
                    <div class="image-card fade-in-up" style="text-align: left; padding: 25px; margin-bottom: 20px;">
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
                            <button class="danger-btn" style="padding: 8px 15px; font-size: 0.85rem; margin-left: 10px;" onclick="deleteAttendance(${sub.id || Date.now()})">Drop</button>
                        </div>
                    </div>
                `;
    });

    const overallPerc = totalClasses > 0 ? ((totalAtt / totalClasses) * 100).toFixed(1) : "0.0";
    const overallEl = document.getElementById('overall-attendance');

    if (overallEl) {
        if (totalClasses === 0) {
            overallEl.innerText = "Overall: 0%";
            overallEl.style.color = "var(--primary)";
        } else {
            overallEl.innerText = `Overall: ${overallPerc}%`;
            overallEl.style.color = overallPerc >= 75 ? "var(--success)" : "var(--danger)";
        }
    }

    if (isLoggedIn) {
        const attEl = document.getElementById('home-att-val');
        const courseEl = document.getElementById('home-course-val');
        if (attEl) attEl.innerText = overallPerc + "%";
        if (courseEl) courseEl.innerText = attendanceData.length;
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
                        <div class="overview-title" style="margin: 20px 0 15px 0;">📊 Detailed Performance</div>
                        ` : ''}
                        ${testsHtml}
                    </div>
                `;
    });

    const overallPercent = grandTotalMax > 0 ? ((grandTotalObtained / grandTotalMax) * 100).toFixed(1) : "0.0";
    const estCGPA = grandTotalMax > 0 ? ((grandTotalObtained / grandTotalMax) * 10).toFixed(2) : "0.00";
    let grade = "C";
    if (overallPercent >= 90) grade = "O"; else if (overallPercent >= 80) grade = "A+";
    else if (overallPercent >= 70) grade = "A"; else if (overallPercent >= 60) grade = "B+";
    else if (overallPercent >= 50) grade = "B";

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
                </div>
            ` + subjectsHTML;
}

// ================= TIMETABLE RENDERER =================
function isClassActive(timeStr) {
    if (!timeStr || !timeStr.includes('-')) return false;
    try {
        let [startStr, endStr] = timeStr.split('-');
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
}

function renderDay(dayNumber, btnElement) {
    document.querySelectorAll('.tt-day-selector .day-btn').forEach(btn => btn.classList.remove('active'));
    if (btnElement) btnElement.classList.add('active');

    const grid = document.getElementById('timetable-grid');
    if (!grid) return;

    const classesForDay = timetableData[dayNumber.toString()] || [];
    grid.innerHTML = '';

    if (classesForDay.length === 0) {
        grid.innerHTML = `<div class="image-card" style="text-align:center; padding: 30px;"><h3 style="color:var(--text-sub); margin:0;">No classes scheduled for Day ${dayNumber}</h3></div>`;
        return;
    }

    // Remove duplicates and fallback "Period" classes if real times exist
    let normalizeStr = (s) => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
    let realSubjects = new Set(classesForDay.filter(c => !String(c.time).toLowerCase().includes('period')).map(c => normalizeStr(c.subject)));

    let deduplicated = classesForDay.filter(c => {
        let isPeriod = String(c.time).toLowerCase().includes('period');
        if (isPeriod && realSubjects.has(normalizeStr(c.subject))) return false;
        return true;
    });

    // Enforce exact uniqueness
    let uniqueSet = new Set();
    deduplicated = deduplicated.filter(c => {
        let str = `${c.time}|${normalizeStr(c.subject)}`;
        if (uniqueSet.has(str)) return false;
        uniqueSet.add(str);
        return true;
    });

    // GROUPING LOGIC FOR IDENTICAL BACK-TO-BACK CLASSES
    let mergedClasses = [];
    deduplicated.forEach(cls => {
        if (mergedClasses.length > 0) {
            let last = mergedClasses[mergedClasses.length - 1];
            if (normalizeStr(last.subject) === normalizeStr(cls.subject) && last.room === cls.room) {
                let start1 = String(last.time).split('-')[0]?.trim() || last.time;
                let end2 = String(cls.time).split('-')[1]?.trim() || String(cls.time).replace(/Period/i, '').trim();
                last.time = `${start1} - ${end2}`;
                return;
            }
        }
        mergedClasses.push({ ...cls });
    });

    mergedClasses.forEach(cls => {
        let isActive = isClassActive(cls.time) && dayNumber == new Date().getDay();
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
}

function changeMonth(dir) {
    currentCalDate.setMonth(currentCalDate.getMonth() + dir);
    renderCalendar();
}

function showEventDetails(dateStr) {
    const card = document.getElementById('cal-event-details');
    card.style.display = 'block';
    card.style.animation = 'none';
    card.offsetHeight; /* trigger reflow */
    card.style.animation = 'fadeInUp 0.4s ease forwards';

    document.getElementById('event-date-title').innerText = new Date(dateStr).toDateString();
    let plan = srmPlanner[dateStr];
    if (plan) {
        let badge = plan.type === 'Holiday' ? '<span class="special-badge" style="background: linear-gradient(135deg, #00cc66, #00994d);">Holiday</span>' : `<span class="special-badge" style="background: linear-gradient(135deg, #bf5af2, #9432c7); text-transform: uppercase;">Day Order ${plan.value}</span>`;
        document.getElementById('event-desc').innerHTML = `${badge} <br><br> ${plan.title || 'No additional details.'}`;
    } else {
        document.getElementById('event-desc').innerText = "No events scheduled for this day.";
    }
}

// ================= GALLERY & PROJECTS =================
const projectsDatabase = {
    'oopsBanner': { title: 'OOPS Banner App', subProjects: [{ id: 'ucsFolder', title: "UC's" }, { id: 'week1Problem', title: 'Week 1 & 2 Problems' }, { id: 'week34Problem', title: 'Week 3 & 4 Problems' }, { id: 'helloAppFolder', title: 'HelloApp UC\'s' }] },
    'ucsFolder': { title: "OOPS Banner App UC's", parent: 'oopsBanner', images: [{ src: 'images/oops-banner/uc1.png', label: '1' }, { src: 'images/oops-banner/uc2.png', label: '2' }, { src: 'images/oops-banner/uc3.png', label: '3' }, { src: 'images/oops-banner/uc4.png', label: '4' }, { src: 'images/oops-banner/uc5.png', label: '5' }, { src: 'images/oops-banner/uc6.png', label: '6' }, { src: 'images/oops-banner/uc7.png', label: '7' }, { src: 'images/oops-banner/uc8.png', label: '8' }, { src: 'images/oops-banner/uc9.png', label: '9' }, { src: 'images/oops-banner/uc10.png', label: '10' }, { src: 'images/oops-banner/end.png', label: 'end' }] },
    'week1Problem': { title: 'Week 1 and 2 Problems', parent: 'oopsBanner', images: [{ src: 'images/oops-banner/Basic-step1.png', label: 'Basic-Step' }, { src: 'images/oops-banner/Basic-step2.png', label: 'Basic-Step' }, { src: 'images/oops-banner/level1.png', label: 'Part 1' }, { src: 'images/oops-banner/level12.png', label: 'Part 2' }, { src: 'images/oops-banner/level13.png', label: 'Part 3' }, { src: 'images/oops-banner/bash.png', label: 'Bash' }, { src: 'images/oops-banner/level21.png', label: 'Part 4' }, { src: 'images/oops-banner/level22.png', label: 'Part 5' }, { src: 'images/oops-banner/level3.png', label: 'Part 6' }] },
    'week34Problem': { title: 'Week 3 and 4 Problems', parent: 'oopsBanner', images: [{ src: 'images/oops-banner/w31.png', label: 'Step1' }, { src: 'images/oops-banner/w32.png', label: 'Step2' }, { src: 'images/oops-banner/w33.png', label: 'Step3' }, { src: 'images/oops-banner/w34.png', label: 'Step4' }, { src: 'images/oops-banner/w35.png', label: 'Step5' }, { src: 'images/oops-banner/w36.png', label: 'Step6' }, { src: 'images/oops-banner/end.png', label: 'end' }] },
    'helloAppFolder': { title: 'HelloApp UC\'s', parent: 'oopsBanner', video: 'https://www.youtube.com/embed/k8eX_rkQxPk', images: [{ src: 'images/oops-banner/ha1.png', label: 'uc 1 Step 1' }, { src: 'images/oops-banner/ha2.png', label: 'Step 2' }, { src: 'images/oops-banner/ha3.png', label: 'Step 3' }, { src: 'images/oops-banner/ha4.png', label: 'Step 4' }, { src: 'images/oops-banner/ha5.png', label: 'uc 2 Step 5' }, { src: 'images/oops-banner/ha6.png', label: 'Step 6' }, { src: 'images/oops-banner/end.png', label: 'end' }] }
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

// ================= STUDY HELPER =================
const helperData = {
    'Semester 1': [{ name: 'Content Adding Soon...', topics: ['Check back later for pyqs.'], pyqLink: '#', ctLink: '#' }],
    'Semester 2': [{ name: 'Content Adding Soon...', topics: ['Check back later for pyqs.'], pyqLink: '#', ctLink: '#' }],
    'Semester 3': [{ name: 'Content Adding Soon...', topics: ['Check back later for pyqs.'], pyqLink: '#', ctLink: '#' }],
    'Semester 4': [{ name: 'Content Adding Soon...', topics: ['Check back later for pyqs.'], pyqLink: '#', ctLink: '#' }]
};
function initHelper() {
    const semContainer = document.getElementById('helper-semesters');
    for (let i = 1; i <= 8; i++) {
        semContainer.innerHTML += `
                    <div class="image-card project-card fade-in-up" onclick="showHelperSubjects('Semester ${i}')">
                        <div class="project-cover" style="height: 150px;"><h2 style="color: var(--primary); margin:0;">SEM ${i}</h2></div>
                    </div>
                `;
    }
}
function showHelperSubjects(semName) {
    document.getElementById('helper-semesters').style.display = 'none';
    document.getElementById('helper-subjects').style.display = 'block';
    document.getElementById('helper-sem-title').innerText = semName;
    const listContainer = document.getElementById('helper-subject-list');
    listContainer.innerHTML = '';
    (helperData[semName] || []).forEach(sub => {
        listContainer.innerHTML += `
                    <details class="fade-in-up">
                        <summary>${sub.name} &#9662;</summary>
                        <div class="details-content">
                            <strong>Important Topics:</strong>
                            <ul style="margin-top: 10px; margin-bottom: 15px;">${sub.topics.map(t => `<li>${t}</li>`).join('')}</ul>
                            <a href="${sub.ctLink}" style="color:var(--primary); text-decoration: none; font-weight: bold;">[ CT Papers ]</a> &nbsp;|&nbsp; 
                            <a href="${sub.pyqLink}" style="color:var(--primary); text-decoration: none; font-weight: bold;">[ PYQs ]</a>
                        </div>
                    </details>
                `;
    });
}
initHelper();

// ================= UTILITIES & HELPERS =================
function updateLiveHighlighting() {
    if (document.getElementById('timetable-view').classList.contains('active')) {
        const dayBtns = document.querySelectorAll('.tt-day-selector .day-btn');
        let activeBtn = null; let activeDay = 1;
        dayBtns.forEach((btn, idx) => { if (btn.classList.contains('active')) { activeBtn = btn; activeDay = idx + 1; } });

        let todayLocal = new Date();
        let tzoffset = todayLocal.getTimezoneOffset() * 60000;
        let localISOTime = (new Date(todayLocal - tzoffset)).toISOString().slice(0, 10);

        let expectedDay = todayLocal.getDay();
        if (srmPlanner[localISOTime] && srmPlanner[localISOTime].type === "Day Order") {
            expectedDay = srmPlanner[localISOTime].value;
        }

        // Only re-refresh the UI if we're currently on today's active schedule
        if (activeDay == expectedDay || (activeDay == todayLocal.getDay())) {
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

setTimeout(() => {
    document.getElementById('splash-screen').classList.add('zoom-out');
    document.getElementById('main-content').classList.add('content-visible');
    document.getElementById('navButtons').style.opacity = '1';
    setTimeout(() => document.getElementById('splash-screen').style.display = 'none', 1000);
    checkAndScheduleNotifications();
}, 1200);

function openLightbox(src) { document.getElementById("lightbox").style.display = "flex"; document.getElementById("lightbox-img").src = src; }
function closeLightbox() { document.getElementById("lightbox").style.display = "none"; }

function requestNotificationPermission() {
    if (!("Notification" in window)) alert("This browser does not support desktop notification");
    else if (Notification.permission === "granted") { alert("Notifications are already enabled!"); checkAndScheduleNotifications(true); }
    else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(permission => {
            if (permission === "granted") alert("Notifications enabled! You will now receive daily mess updates.");
        });
    }
}

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
        notifiedEvents = { breakfast: false, lunch: false, snacks: false, dinner: false, sleep: false };
        localStorage.setItem('lastNotifiedDate', now.toDateString());
    }

    if (timeFloat >= 6.5 && timeFloat < 10 && !notifiedEvents.breakfast) { triggerLocalNotification("Good Morning! ☀️ Breakfast:", todaysMenu.Breakfast); notifiedEvents.breakfast = true; }
    if (timeFloat >= 11 && timeFloat < 14 && !notifiedEvents.lunch) { triggerLocalNotification("Lunch Time Approaching! 🍛", todaysMenu.Lunch); notifiedEvents.lunch = true; }
    if (timeFloat >= 15 && timeFloat < 18 && !notifiedEvents.snacks) { triggerLocalNotification("Snack Time! 🥨", todaysMenu.Snacks); notifiedEvents.snacks = true; }
    if (timeFloat >= 18.5 && timeFloat < 21 && !notifiedEvents.dinner) { triggerLocalNotification("Dinner is served! 🍽️", todaysMenu.Dinner); notifiedEvents.dinner = true; }
    if (timeFloat >= 22.5 && !notifiedEvents.sleep) { triggerLocalNotification("Time to Sleep! 🌙", "Put the phone away and get some rest for classes tomorrow. 💤"); notifiedEvents.sleep = true; }

    localStorage.setItem('notifiedEvents', JSON.stringify(notifiedEvents));
    if (force && timeFloat < 6.5) triggerLocalNotification("SRM Hub Active", "Notifications are active. Next alert will be at 6:30 AM! ⏰");
}
