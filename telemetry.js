// Error reporting through Sentry, inlined into every tool's <head> by
// scripts/publish_tools.py so it runs before the tool's own code.
//
// Tools work on text people paste or type, and keep it in the URL and in
// localStorage, so this sends as little as it can: an error's type and stack
// trace, the page's path, the tool's name (as a `tool` tag), the browser and
// the release. Never error messages, query strings or fragments, breadcrumbs,
// IP addresses or session replays.
// tests/test_telemetry.py checks that nothing typed into a tool reaches Sentry.
//
// A tool with <body data-no-telemetry> doesn't get this script at all, and
// so records nothing. Anything added here later has to respect that too.
(() => {
  // The tools project's DSN. While it's empty, nothing loads and nothing is sent.
  const SENTRY_DSN = '';
  const SDK = {
    src: 'https://browser.sentry-cdn.com/11.10.0/bundle.min.js',
    integrity: 'sha384-O/8YQaGGVy/n9jIUzcOiaiJVm4t5+JMNiK/zOa0fWvlSld+FquXemEcwJxQ3x/Lr',
  };

  // Local previews and the tests report nothing.
  if (!SENTRY_DSN || location.hostname !== 'tools.michaelwarkentin.com') return;

  const release = document.currentScript?.dataset.release || undefined;
  const withoutQuery = (url) => url?.replace(/[?#].*$/, '');
  const tool = location.pathname.split('/').pop().replace(/\.html$/, '');

  // Only these fields leave the page. Messages are dropped because they can
  // quote input: JSON.parse, for one, puts the start of the text it rejected
  // in its message. The type, stack trace and source on GitHub are enough to
  // find the line that broke.
  const scrub = (event) => ({
    event_id: event.event_id,
    timestamp: event.timestamp,
    platform: event.platform,
    level: event.level,
    release: event.release,
    environment: event.environment,
    sdk: event.sdk,
    tags: { tool },
    request: { url: withoutQuery(location.href), headers: { 'User-Agent': navigator.userAgent } },
    exception: {
      values: (event.exception?.values ?? []).map(({ type, mechanism, stacktrace }) => ({
        type,
        mechanism: mechanism && { type: mechanism.type, handled: mechanism.handled },
        stacktrace: stacktrace && {
          frames: (stacktrace.frames ?? []).map((frame) => ({
            filename: withoutQuery(frame.filename),
            function: frame.function,
            lineno: frame.lineno,
            colno: frame.colno,
            in_app: frame.in_app,
          })),
        },
      })),
    },
  });

  // Errors from before the SDK arrives are kept and sent once it does.
  // Errors from cross-origin scripts arrive as "Script error." with no error
  // attached; Sentry ignores those too.
  const early = [];
  const keep = (event) => {
    if (event.error || 'reason' in event) early.push(event.error ?? event.reason);
  };
  addEventListener('error', keep);
  addEventListener('unhandledrejection', keep);

  const script = document.createElement('script');
  Object.assign(script, { src: SDK.src, integrity: SDK.integrity, crossOrigin: 'anonymous' });
  script.onload = () => {
    removeEventListener('error', keep);
    removeEventListener('unhandledrejection', keep);
    Sentry.init({
      dsn: SENTRY_DSN,
      release,
      // Breadcrumbs record console output, clicks, requests and URLs.
      integrations: (defaults) => defaults.filter((integration) => integration.name !== 'Breadcrumbs'),
      dataCollection: { userInfo: false },
      beforeSend: scrub,
    });
    early.forEach((error) => Sentry.captureException(error, { mechanism: { handled: false } }));
  };
  document.head.append(script);
})();
