/**
 * Student Information Management System (SIMS)
 * Client-side interactivity, responsive toggles, modal handling, and helpers.
 */

document.addEventListener('DOMContentLoaded', () => {

  // --------------------------------------------------------------------------
  // 1. Mobile Sidebar Navigation Toggle
  // --------------------------------------------------------------------------
  const sidebar = document.querySelector('.sidebar');
  const sidebarToggleBtn = document.querySelector('.sidebar-toggle-btn');
  const sidebarOverlay = document.querySelector('.sidebar-overlay');

  if (sidebarToggleBtn && sidebar && sidebarOverlay) {
    sidebarToggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      sidebarOverlay.classList.toggle('active');
    });

    sidebarOverlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      sidebarOverlay.classList.remove('active');
    });
  }

  // --------------------------------------------------------------------------
  // 2. Modal Controller
  // --------------------------------------------------------------------------
  window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    }
  };

  // Close modals on clicking backdrop or close buttons
  document.querySelectorAll('.modal-backdrop').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
      }
    });

    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        modal.classList.remove('active');
        document.body.style.overflow = '';
      });
    }
  });

  // Close modals on ESC key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.active').forEach(modal => {
        modal.classList.remove('active');
      });
      document.body.style.overflow = '';
    }
  });

  // --------------------------------------------------------------------------
  // 3. Auto-Dismiss Flash Alerts
  // --------------------------------------------------------------------------
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 400);
    }, 5000);
  });

  // --------------------------------------------------------------------------
  // 4. Form Submission Loading Indicators
  // --------------------------------------------------------------------------
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function(e) {
      // Avoid disabling if form validation fails
      if (!this.checkValidity()) return;

      const submitBtn = this.querySelector('button[type="submit"]');
      if (submitBtn && !submitBtn.classList.contains('no-loading')) {
        const originalText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        
        // Safety timeout in case navigation is delayed
        setTimeout(() => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalText;
        }, 8000);
      }
    });
  });

  // --------------------------------------------------------------------------
  // 5. Attendance Shortcuts: "Mark All Present" & "Mark All Absent"
  // --------------------------------------------------------------------------
  window.markAllAttendance = function(status) {
    const radios = document.querySelectorAll(`input[type="radio"][value="${status}"]`);
    radios.forEach(radio => {
      radio.checked = true;
    });
  };

  // --------------------------------------------------------------------------
  // 6. Demo Account Quick-Fill on Login Page
  // --------------------------------------------------------------------------
  window.fillDemoLogin = function(role) {
    const userField = document.getElementById('username');
    const passField = document.getElementById('password');
    if (!userField || !passField) return;

    if (role === 'admin') {
      userField.value = 'admin';
      passField.value = 'admin123';
    } else if (role === 'faculty') {
      userField.value = 'prof_smith';
      passField.value = 'faculty123';
    } else if (role === 'student') {
      userField.value = 'CS202601';
      passField.value = 'student123';
    }

    userField.focus();
  };

  // --------------------------------------------------------------------------
  // 7. Dynamic Modal Pre-Fill Functions
  // --------------------------------------------------------------------------

  // Edit Student Modal Pre-fill
  window.editStudentModal = function(id, name, rollNo, sClass, dob, contact, address) {
    const form = document.getElementById('editStudentForm');
    if (!form) return;
    form.action = `/admin/students/edit/${id}`;
    document.getElementById('edit_student_name').value = name;
    document.getElementById('edit_student_roll_no').value = rollNo;
    document.getElementById('edit_student_class').value = sClass;
    document.getElementById('edit_student_dob').value = dob || '';
    document.getElementById('edit_student_contact').value = contact || '';
    document.getElementById('edit_student_address').value = address || '';
    openModal('editStudentModal');
  };

  // Edit Faculty Modal Pre-fill
  window.editFacultyModal = function(id, name, subject, contact) {
    const form = document.getElementById('editFacultyForm');
    if (!form) return;
    form.action = `/admin/faculty/edit/${id}`;
    document.getElementById('edit_faculty_name').value = name;
    document.getElementById('edit_faculty_subject').value = subject || '';
    document.getElementById('edit_faculty_contact').value = contact || '';
    openModal('editFacultyModal');
  };

  // Edit Course Modal Pre-fill
  window.editCourseModal = function(id, name, cClass, facultyId) {
    const form = document.getElementById('editCourseForm');
    if (!form) return;
    form.action = `/admin/courses/edit/${id}`;
    document.getElementById('edit_course_name').value = name;
    document.getElementById('edit_course_class').value = cClass;
    document.getElementById('edit_course_faculty').value = facultyId || '';
    openModal('editCourseModal');
  };

  // Record Payment Modal Pre-fill
  window.recordPaymentModal = function(feeId, studentName, rollNo, dueAmount, paidAmount) {
    const form = document.getElementById('recordPaymentForm');
    if (!form) return;
    form.action = `/admin/fees/pay/${feeId}`;
    const pending = Math.max(0, dueAmount - paidAmount);
    document.getElementById('pay_student_display').textContent = `${studentName} (${rollNo})`;
    document.getElementById('pay_due_display').textContent = `₹${dueAmount.toFixed(2)}`;
    document.getElementById('pay_pending_display').textContent = `₹${pending.toFixed(2)}`;
    document.getElementById('payment_amount').value = pending > 0 ? pending : '';
    document.getElementById('payment_amount').max = pending;
    openModal('recordPaymentModal');
  };

  // --------------------------------------------------------------------------
  // 8. Instant Client-Side Search Filter (for tables with .filterable-table)
  // --------------------------------------------------------------------------
  const clientSearchInput = document.getElementById('instantTableSearch');
  if (clientSearchInput) {
    clientSearchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();
      const rows = document.querySelectorAll('.filterable-table tbody tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }

});
