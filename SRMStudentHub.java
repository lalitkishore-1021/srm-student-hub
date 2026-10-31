import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.border.LineBorder;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;

/**
 * SRM Student Hub - Attendance & Margin Calculator
 * Desktop Java Swing Component for Java Lab / Project Evaluation
 */
public class SRMStudentHub {

    public static void main(String[] args) {
        // Set modern system look and feel if available
        try {
            UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
        } catch (Exception ignored) {}

        // 1. Create the main application window (JFrame)
        JFrame frame = new JFrame("SRM Student Hub - Attendance & Margin Engine");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(620, 680);
        frame.setResizable(false);
        frame.setLocationRelativeTo(null); // Center on screen
        frame.setLayout(new BorderLayout(10, 10));

        // -------------------------------------------------------------
        // HEADER PANEL (Title & Subtitle)
        // -------------------------------------------------------------
        JPanel headerPanel = new JPanel();
        headerPanel.setLayout(new BoxLayout(headerPanel, BoxLayout.Y_AXIS));
        headerPanel.setBackground(new Color(24, 43, 73)); // SRM Navy Blue
        headerPanel.setBorder(new EmptyBorder(16, 20, 16, 20));

        JLabel titleLabel = new JLabel("SRM STUDENT HUB");
        titleLabel.setFont(new Font("Segoe UI", Font.BOLD, 22));
        titleLabel.setForeground(Color.WHITE);
        titleLabel.setAlignmentX(Component.CENTER_ALIGNMENT);

        JLabel subTitleLabel = new JLabel("Java Swing GUI Module - Attendance & Margin Calculator");
        subTitleLabel.setFont(new Font("Segoe UI", Font.PLAIN, 13));
        subTitleLabel.setForeground(new Color(200, 220, 255));
        subTitleLabel.setAlignmentX(Component.CENTER_ALIGNMENT);

        headerPanel.add(titleLabel);
        headerPanel.add(Box.createRigidArea(new Dimension(0, 4)));
        headerPanel.add(subTitleLabel);

        frame.add(headerPanel, BorderLayout.NORTH);

        // -------------------------------------------------------------
        // CENTER FORM PANEL (Inputs & Controls)
        // -------------------------------------------------------------
        JPanel mainContentPanel = new JPanel();
        mainContentPanel.setLayout(new BoxLayout(mainContentPanel, BoxLayout.Y_AXIS));
        mainContentPanel.setBorder(new EmptyBorder(10, 20, 15, 20));
        mainContentPanel.setBackground(new Color(245, 247, 250));

        // Quick Preset Selector
        JPanel presetPanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 4));
        presetPanel.setBackground(new Color(245, 247, 250));
        JLabel presetLabel = new JLabel("Quick Course Preset:");
        presetLabel.setFont(new Font("Segoe UI", Font.BOLD, 12));
        String[] sampleCourses = {
            "-- Select Sample SRM Subject --",
            "21CSC205J - Object Oriented Programming in Java (18/20)",
            "21CSC204J - Design & Analysis of Algorithms (24/36)",
            "21MAT201J - Calculus & Linear Algebra (45/50)",
            "21CSC203J - Database Management Systems (15/22)"
        };
        JComboBox<String> courseDropdown = new JComboBox<>(sampleCourses);
        courseDropdown.setFont(new Font("Segoe UI", Font.PLAIN, 12));
        presetPanel.add(presetLabel);
        presetPanel.add(courseDropdown);
        mainContentPanel.add(presetPanel);

        // Input Form Fields (Grid Layout)
        JPanel formGrid = new JPanel(new GridLayout(4, 2, 10, 12));
        formGrid.setBackground(new Color(245, 247, 250));
        formGrid.setBorder(BorderFactory.createCompoundBorder(
            new LineBorder(new Color(220, 226, 235), 1, true),
            new EmptyBorder(14, 16, 14, 16)
        ));

        // 1. Course Name
        JLabel lblCourse = new JLabel("Course Name / Code:");
        lblCourse.setFont(new Font("Segoe UI", Font.BOLD, 13));
        JTextField txtCourse = new JTextField("21CSC205J - Java Programming");
        txtCourse.setFont(new Font("Segoe UI", Font.PLAIN, 13));

        // 2. Conducted Hours
        JLabel lblConducted = new JLabel("Total Hours Conducted:");
        lblConducted.setFont(new Font("Segoe UI", Font.BOLD, 13));
        JTextField txtConducted = new JTextField("20");
        txtConducted.setFont(new Font("Segoe UI", Font.PLAIN, 13));

        // 3. Attended Hours
        JLabel lblAttended = new JLabel("Hours Attended (Present):");
        lblAttended.setFont(new Font("Segoe UI", Font.BOLD, 13));
        JTextField txtAttended = new JTextField("18");
        txtAttended.setFont(new Font("Segoe UI", Font.PLAIN, 13));

        // 4. Target Percentage
        JLabel lblTarget = new JLabel("Target Attendance %:");
        lblTarget.setFont(new Font("Segoe UI", Font.BOLD, 13));
        JTextField txtTarget = new JTextField("75");
        txtTarget.setFont(new Font("Segoe UI", Font.PLAIN, 13));

        formGrid.add(lblCourse);
        formGrid.add(txtCourse);
        formGrid.add(lblConducted);
        formGrid.add(txtConducted);
        formGrid.add(lblAttended);
        formGrid.add(txtAttended);
        formGrid.add(lblTarget);
        formGrid.add(txtTarget);

        mainContentPanel.add(Box.createRigidArea(new Dimension(0, 8)));
        mainContentPanel.add(formGrid);

        // -------------------------------------------------------------
        // BUTTONS PANEL (Event Listeners)
        // -------------------------------------------------------------
        JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.CENTER, 12, 12));
        buttonPanel.setBackground(new Color(245, 247, 250));

        JButton btnCalculate = new JButton("Calculate Margin");
        btnCalculate.setFont(new Font("Segoe UI", Font.BOLD, 13));
        btnCalculate.setBackground(new Color(26, 115, 232));
        btnCalculate.setForeground(Color.WHITE);
        btnCalculate.setFocusPainted(false);
        btnCalculate.setCursor(new Cursor(Cursor.HAND_CURSOR));

        JButton btnSimulate = new JButton("+1 Miss Simulation");
        btnSimulate.setFont(new Font("Segoe UI", Font.PLAIN, 13));
        btnSimulate.setFocusPainted(false);
        btnSimulate.setCursor(new Cursor(Cursor.HAND_CURSOR));

        JButton btnReset = new JButton("Reset");
        btnReset.setFont(new Font("Segoe UI", Font.PLAIN, 13));
        btnReset.setFocusPainted(false);
        btnReset.setCursor(new Cursor(Cursor.HAND_CURSOR));

        buttonPanel.add(btnCalculate);
        buttonPanel.add(btnSimulate);
        buttonPanel.add(btnReset);
        mainContentPanel.add(buttonPanel);

        // -------------------------------------------------------------
        // RESULT CARD PANEL (Displays calculations)
        // -------------------------------------------------------------
        JPanel resultCard = new JPanel();
        resultCard.setLayout(new BoxLayout(resultCard, BoxLayout.Y_AXIS));
        resultCard.setBackground(Color.WHITE);
        resultCard.setBorder(BorderFactory.createCompoundBorder(
            new LineBorder(new Color(205, 215, 228), 1, true),
            new EmptyBorder(16, 20, 16, 20)
        ));

        JLabel resultTitle = new JLabel("CALCULATION RESULTS");
        resultTitle.setFont(new Font("Segoe UI", Font.BOLD, 12));
        resultTitle.setForeground(new Color(110, 125, 145));
        resultTitle.setAlignmentX(Component.CENTER_ALIGNMENT);

        JLabel percentLabel = new JLabel("Attendance: -- %");
        percentLabel.setFont(new Font("Segoe UI", Font.BOLD, 26));
        percentLabel.setForeground(new Color(24, 43, 73));
        percentLabel.setAlignmentX(Component.CENTER_ALIGNMENT);

        JLabel statusBadge = new JLabel("Ready - Click Calculate");
        statusBadge.setFont(new Font("Segoe UI", Font.BOLD, 14));
        statusBadge.setForeground(new Color(70, 80, 95));
        statusBadge.setAlignmentX(Component.CENTER_ALIGNMENT);

        JLabel detailLabel = new JLabel("Enter conducted and attended hours above.");
        detailLabel.setFont(new Font("Segoe UI", Font.PLAIN, 13));
        detailLabel.setForeground(new Color(100, 110, 125));
        detailLabel.setAlignmentX(Component.CENTER_ALIGNMENT);

        resultCard.add(resultTitle);
        resultCard.add(Box.createRigidArea(new Dimension(0, 8)));
        resultCard.add(percentLabel);
        resultCard.add(Box.createRigidArea(new Dimension(0, 6)));
        resultCard.add(statusBadge);
        resultCard.add(Box.createRigidArea(new Dimension(0, 6)));
        resultCard.add(detailLabel);

        mainContentPanel.add(resultCard);
        frame.add(mainContentPanel, BorderLayout.CENTER);

        // -------------------------------------------------------------
        // FOOTER PANEL
        // -------------------------------------------------------------
        JPanel footerPanel = new JPanel(new FlowLayout(FlowLayout.CENTER));
        footerPanel.setBackground(new Color(238, 242, 246));
        JLabel footerLabel = new JLabel("SRM Student Hub  |  Java Swing GUI Component  |  Academic Engine");
        footerLabel.setFont(new Font("Segoe UI", Font.ITALIC, 11));
        footerLabel.setForeground(new Color(120, 130, 145));
        footerPanel.add(footerLabel);
        frame.add(footerPanel, BorderLayout.SOUTH);

        // -------------------------------------------------------------
        // LOGIC & EVENT HANDLING (ActionListener Implementations)
        // -------------------------------------------------------------

        // 1. Calculate Margin Action
        btnCalculate.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                try {
                    int conducted = Integer.parseInt(txtConducted.getText().trim());
                    int attended = Integer.parseInt(txtAttended.getText().trim());
                    double target = Double.parseDouble(txtTarget.getText().trim());

                    if (conducted <= 0) {
                        JOptionPane.showMessageDialog(frame, "Conducted hours must be greater than 0.", "Input Error", JOptionPane.WARNING_MESSAGE);
                        return;
                    }
                    if (attended > conducted) {
                        JOptionPane.showMessageDialog(frame, "Attended hours cannot exceed conducted hours.", "Input Error", JOptionPane.WARNING_MESSAGE);
                        return;
                    }
                    if (attended < 0) {
                        JOptionPane.showMessageDialog(frame, "Attended hours cannot be negative.", "Input Error", JOptionPane.WARNING_MESSAGE);
                        return;
                    }

                    // Formula: (Attended / Conducted) * 100
                    double currentPct = ((double) attended / conducted) * 100.0;
                    percentLabel.setText(String.format("Attendance: %.1f%%", currentPct));

                    double targetDecimal = target / 100.0;

                    if (currentPct >= target) {
                        // Safe: Calculate bunk margin
                        int safeMargin = (int) Math.floor((attended - (targetDecimal * conducted)) / targetDecimal);
                        if (safeMargin < 0) safeMargin = 0;

                        percentLabel.setForeground(new Color(24, 134, 75)); // Green
                        statusBadge.setText("SAFE ZONE (Above " + (int)target + "%)");
                        statusBadge.setForeground(new Color(24, 134, 75));
                        detailLabel.setText("You can safely miss " + safeMargin + " more class(es) and remain above " + (int)target + "%.");
                    } else {
                        // Shortage: Calculate required classes
                        int needed = (int) Math.ceil(((targetDecimal * conducted) - attended) / (1.0 - targetDecimal));
                        if (needed < 0) needed = 0;

                        // Calculate projected date when required becomes 0
                        java.time.LocalDate targetDate = java.time.LocalDate.now();
                        int daysAdded = 0;
                        int hoursCovered = 0;
                        while (hoursCovered < needed && daysAdded < 120) {
                            targetDate = targetDate.plusDays(1);
                            daysAdded++;
                            java.time.DayOfWeek dow = targetDate.getDayOfWeek();
                            if (dow != java.time.DayOfWeek.SATURDAY && dow != java.time.DayOfWeek.SUNDAY) {
                                hoursCovered++;
                            }
                        }
                        String dateFormatted = targetDate.format(java.time.format.DateTimeFormatter.ofPattern("EEE, MMM d, yyyy"));

                        percentLabel.setForeground(new Color(217, 48, 37)); // Red
                        statusBadge.setText("ATTENDANCE SHORTAGE (< " + (int)target + "%)");
                        statusBadge.setForeground(new Color(217, 48, 37));
                        detailLabel.setText("<html><center>Attend next <b>" + needed + "</b> class(es) for " + (int)target + "% &nbsp;•&nbsp; "
                                + "<font color='#008844'><b>Safe by: " + dateFormatted + "</b></font></center></html>");
                    }
                } catch (NumberFormatException ex) {
                    JOptionPane.showMessageDialog(frame, "Please enter valid numeric values for hours and target %.", "Invalid Input", JOptionPane.ERROR_MESSAGE);
                }
            }
        });

        // 2. Simulate Next Class Missed (+1 Conducted, +0 Attended)
        btnSimulate.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                try {
                    int conducted = Integer.parseInt(txtConducted.getText().trim()) + 1;
                    int attended = Integer.parseInt(txtAttended.getText().trim());
                    txtConducted.setText(String.valueOf(conducted));
                    btnCalculate.doClick(); // Recalculate
                } catch (NumberFormatException ex) {
                    JOptionPane.showMessageDialog(frame, "Please check the entered values first.", "Error", JOptionPane.ERROR_MESSAGE);
                }
            }
        });

        // 3. Reset Button Action
        btnReset.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                txtCourse.setText("");
                txtConducted.setText("");
                txtAttended.setText("");
                txtTarget.setText("75");
                courseDropdown.setSelectedIndex(0);
                percentLabel.setText("Attendance: -- %");
                percentLabel.setForeground(new Color(24, 43, 73));
                statusBadge.setText("Ready - Click Calculate");
                statusBadge.setForeground(new Color(70, 80, 95));
                detailLabel.setText("Enter conducted and attended hours above.");
            }
        });

        // 4. Quick Sample Course Dropdown
        courseDropdown.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                int idx = courseDropdown.getSelectedIndex();
                if (idx == 1) {
                    txtCourse.setText("21CSC205J - Object Oriented Programming in Java");
                    txtConducted.setText("20");
                    txtAttended.setText("18");
                    txtTarget.setText("75");
                    btnCalculate.doClick();
                } else if (idx == 2) {
                    txtCourse.setText("21CSC204J - Design & Analysis of Algorithms");
                    txtConducted.setText("36");
                    txtAttended.setText("24");
                    txtTarget.setText("75");
                    btnCalculate.doClick();
                } else if (idx == 3) {
                    txtCourse.setText("21MAT201J - Calculus & Linear Algebra");
                    txtConducted.setText("50");
                    txtAttended.setText("45");
                    txtTarget.setText("75");
                    btnCalculate.doClick();
                } else if (idx == 4) {
                    txtCourse.setText("21CSC203J - Database Management Systems");
                    txtConducted.setText("22");
                    txtAttended.setText("15");
                    txtTarget.setText("75");
                    btnCalculate.doClick();
                }
            }
        });

        // Trigger initial calculation
        btnCalculate.doClick();

        // 5. Display window
        frame.setVisible(true);
    }
}
