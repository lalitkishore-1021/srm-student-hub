import express from 'express';
import cors from 'cors';
// Importing the official bypass functions
import { verifyPassword, getAttendance, getMarks, getTimetable } from 'srm-academia-api';

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static('.')); // Serves your index.html and images

app.post('/api/mega-sync', async (req, res) => {
    let { email, password } = req.body;
    
    // Auto-append the domain so students can just type "bl9209"
    if (!email.includes('@srmist.edu.in')) {
        email = email + '@srmist.edu.in';
    }

    try {
        console.log(`[${email}] Initiating CAPTCHA-free Login...`);
        
        // Step 1: Securely verify user and get the session cookie
        const authData = await verifyPassword(email, password);
        
        if (authData.error || authData.status !== 200) {
            return res.status(401).json({ success: false, error: 'Invalid SRM Email or Password' });
        }
        
        // The API returns the required session cookies 
        const cookies = authData.cookies || authData.token; 

        console.log(`[${email}] Login Success! Fetching Mega-Sync Data...`);

        // Step 2: Fetch everything simultaneously for maximum speed
        const [attendanceRes, marksRes, timetableRes] = await Promise.all([
            getAttendance(cookies),
            getMarks(cookies),
            getTimetable(cookies)
        ]);

        console.log(`[${email}] Mega-Sync Complete! Sending to phone.`);

        // Step 3: Send the massive data package back to the frontend
        res.json({
            success: true,
            data: {
                attendance: attendanceRes.attendance || [],
                marks: marksRes.marks || [],
                timetable: timetableRes.timetable || []
            }
        });

    } catch (err) {
        console.error('Mega-Sync Failed:', err);
        res.status(500).json({ success: false, error: 'Failed to connect to SRM Servers.' });
    }
});

const PORT = process.env.PORT || 5001;
app.listen(PORT, () => console.log(`🚀 Node.js SRM Hub API running on port ${PORT}`));