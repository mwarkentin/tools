// Shared footer, added to every tool at build time by scripts/publish_tools.py.
// Links home, to this tool's entry in the colophon, to its source on GitHub
// and, once TIP_URL is set, to the tip jar.
// A tool can opt out with <body data-hide-footer>.
const REPO_URL = 'https://github.com/mwarkentin/tools';
// The Stripe Payment Link for tips. While it's empty there's no tip link.
// Keep it the same as TIP_URL in scripts/common.py.
const TIP_URL = '';

const slug = location.pathname.split('/').pop().replace(/\.html$/, '');

// The tip link tells Stripe which tool it came from. client_reference_id
// allows only letters, digits, dashes and underscores; Stripe drops anything else.
function tipLink(source) {
  const url = new URL(TIP_URL);
  url.searchParams.set('client_reference_id', source.replace(/[^\w-]/g, '_'));
  return url.href;
}

if (/^[\w.-]+$/.test(slug) && !('hideFooter' in document.body.dataset)) {
  const file = `${slug}.html`;
  const links = [
    ['Home', '/'],
    ['About this tool', `/colophon#${file}`],
    ['Source', `${REPO_URL}/blob/main/${file}`],
  ];
  if (TIP_URL) links.push(['Tip jar', tipLink(`tools-${slug}`)]);

  const footer = document.createElement('footer');
  footer.dataset.toolsFooter = '';
  // Inline styles so a tool's own CSS can't restyle the footer by accident.
  footer.style.cssText = [
    'grid-column: 1 / -1',
    'box-sizing: border-box',
    'width: 100%',
    'margin: 3rem 0 0',
    'padding: 1rem 16px calc(1rem + env(safe-area-inset-bottom))',
    'border-top: 1px solid color-mix(in srgb, currentColor 20%, transparent)',
    'font: 14px/1.5 system-ui, -apple-system, sans-serif',
    'text-align: center',
    'opacity: 0.75',
  ].join(';');

  links.forEach(([text, href], index) => {
    if (index > 0) footer.append(' · ');
    const link = document.createElement('a');
    link.href = href;
    link.textContent = text;
    link.style.cssText = 'color: inherit; text-decoration: underline; text-underline-offset: 2px';
    footer.append(link);
  });

  document.body.append(footer);
}
