const yearEl = document.getElementById('year');
if (yearEl) {
  yearEl.textContent = String(new Date().getFullYear());
}

const form = document.querySelector('.contact-form');
const statusEl = document.getElementById('form-status');

if (form && statusEl) {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    statusEl.textContent = 'Thanks! We will reach out within one business day.';
    form.reset();
  });
}
