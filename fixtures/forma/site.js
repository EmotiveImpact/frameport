document.querySelectorAll('[aria-controls]').forEach(button => button.addEventListener('click', () => {
 const target = document.getElementById(button.getAttribute('aria-controls'));
 const expanded = button.getAttribute('aria-expanded') === 'true';
 button.setAttribute('aria-expanded',String(!expanded)); target.hidden = expanded;
}));
