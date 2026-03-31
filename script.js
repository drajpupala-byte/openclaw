/* ============================================
   Navbar: scroll behavior & active links
   ============================================ */
const navbar = document.getElementById('navbar');
const navLinks = document.querySelectorAll('.nav-links a');
const sections = document.querySelectorAll('section[id]');

window.addEventListener('scroll', () => {
  // Sticky shadow
  if (window.scrollY > 40) {
    navbar.classList.add('scrolled');
  } else {
    navbar.classList.remove('scrolled');
  }

  // Active nav link highlighting
  let current = '';
  sections.forEach(section => {
    const sectionTop = section.offsetTop - 100;
    if (window.scrollY >= sectionTop) {
      current = section.getAttribute('id');
    }
  });

  navLinks.forEach(link => {
    link.classList.remove('active');
    if (link.getAttribute('href') === `#${current}`) {
      link.classList.add('active');
    }
  });
});

/* ============================================
   Hamburger mobile menu
   ============================================ */
const hamburger = document.getElementById('hamburger');
const navLinksEl = document.getElementById('nav-links');

hamburger.addEventListener('click', () => {
  hamburger.classList.toggle('open');
  navLinksEl.classList.toggle('open');
});

// Close menu when a link is clicked
navLinksEl.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    hamburger.classList.remove('open');
    navLinksEl.classList.remove('open');
  });
});

/* ============================================
   Theme Toggle
   ============================================ */
const themeToggle = document.getElementById('theme-toggle');
const themeIcon = themeToggle.querySelector('.theme-icon');

const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);
updateThemeIcon(savedTheme);

themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeIcon(next);
});

function updateThemeIcon(theme) {
  themeIcon.innerHTML = theme === 'dark' ? '&#9728;' : '&#9790;';
}

/* ============================================
   Typewriter effect
   ============================================ */
const typedEl = document.getElementById('typed-text');
const phrases = [
  'Full Stack Developer',
  'Open Source Enthusiast',
  'Problem Solver',
  'UI/UX Advocate',
];

let phraseIndex = 0;
let charIndex = 0;
let isDeleting = false;
let typingSpeed = 80;

function type() {
  const currentPhrase = phrases[phraseIndex];

  if (!isDeleting) {
    typedEl.textContent = currentPhrase.slice(0, charIndex + 1);
    charIndex++;
    if (charIndex === currentPhrase.length) {
      isDeleting = true;
      typingSpeed = 2000; // pause before deleting
    } else {
      typingSpeed = 80;
    }
  } else {
    typedEl.textContent = currentPhrase.slice(0, charIndex - 1);
    charIndex--;
    typingSpeed = 40;
    if (charIndex === 0) {
      isDeleting = false;
      phraseIndex = (phraseIndex + 1) % phrases.length;
      typingSpeed = 300;
    }
  }

  setTimeout(type, typingSpeed);
}

// Add cursor span
const cursor = document.createElement('span');
cursor.className = 'cursor';
typedEl.insertAdjacentElement('afterend', cursor);
type();

/* ============================================
   Scroll-triggered fade-in animations
   ============================================ */
const fadeTargets = [
  '.about-grid',
  '.skill-category',
  '.project-card',
  '.contact-grid',
  '.section-title',
  '.section-subtitle',
];

fadeTargets.forEach(selector => {
  document.querySelectorAll(selector).forEach(el => {
    el.classList.add('fade-in');
  });
});

const observer = new IntersectionObserver(
  entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.12 }
);

document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

/* ============================================
   Contact Form (demo handler)
   ============================================ */
const form = document.getElementById('contact-form');
const formStatus = document.getElementById('form-status');

form.addEventListener('submit', e => {
  e.preventDefault();

  const name = form.name.value.trim();
  const email = form.email.value.trim();
  const message = form.message.value.trim();

  if (!name || !email || !message) {
    formStatus.textContent = 'Please fill in all fields.';
    formStatus.className = 'form-status error';
    return;
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    formStatus.textContent = 'Please enter a valid email address.';
    formStatus.className = 'form-status error';
    return;
  }

  // Simulate sending
  const submitBtn = form.querySelector('[type="submit"]');
  submitBtn.textContent = 'Sending...';
  submitBtn.disabled = true;

  setTimeout(() => {
    formStatus.textContent = 'Message sent! I\'ll get back to you soon.';
    formStatus.className = 'form-status success';
    form.reset();
    submitBtn.textContent = 'Send Message';
    submitBtn.disabled = false;

    setTimeout(() => {
      formStatus.textContent = '';
      formStatus.className = 'form-status';
    }, 5000);
  }, 1200);
});

/* ============================================
   Footer year
   ============================================ */
document.getElementById('year').textContent = new Date().getFullYear();
