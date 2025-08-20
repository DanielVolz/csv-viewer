import { useEffect, useRef } from 'react';
import { toast } from 'react-toastify';

// Polls index.html headers to detect a new deployment and prompts the user to refresh
export default function useUpdateNotifier({ intervalMs = 60000 } = {}) {
  const baselineRef = useRef({ etag: null, lastModified: null, set: false });
  const notifiedRef = useRef(false);
  const toastIdRef = useRef(null);

  useEffect(() => {
    // In test environments, completely no-op to avoid timers/open handles
    if (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'test') {
      return () => { };
    }
    let timer;

    const showNow = () => {
      if (notifiedRef.current) return;
      notifiedRef.current = true;
      const Content = () => {
        const handleRefreshClick = () => {
          // Dismiss toast first
          try { if (toastIdRef.current) toast.dismiss(toastIdRef.current); } catch { }
          // Remove forcing params so it doesn't re-trigger after reload
          try {
            const url = new URL(window.location.href);
            url.searchParams.delete('showUpdateToast');
            url.searchParams.delete('forceUpdate');
            window.history.replaceState(null, '', url.toString());
          } catch { }
          // Reload the page
          window.location.reload();
        };
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span>Neue Version verfügbar. Jetzt aktualisieren?</span>
            <button
              type="button"
              onClick={handleRefreshClick}
              style={{
                background: '#1976d2', color: '#fff', border: 0, borderRadius: 6,
                padding: '6px 12px', cursor: 'pointer', fontWeight: 600,
                whiteSpace: 'nowrap'
              }}
            >
              Refresh
            </button>
          </div>
        );
      };
      toastIdRef.current = toast.info(<Content />, { autoClose: false, closeOnClick: false });
    };

    const check = async (forceDetect = false) => {
      try {
        // Prefer checking /index.html; fall back to root if not found
        let res = await fetch('/index.html', { method: 'HEAD', cache: 'no-store' });
        if (!res.ok) {
          res = await fetch('/', { method: 'HEAD', cache: 'no-store' });
        }
        const etag = res.headers.get('etag');
        const lastModified = res.headers.get('last-modified');

        if (!baselineRef.current.set && !forceDetect) {
          baselineRef.current = { etag, lastModified, set: true };
          return;
        }

        const changed = (etag && etag !== baselineRef.current.etag) ||
          (!etag && lastModified && lastModified !== baselineRef.current.lastModified);

        if (changed && !notifiedRef.current) {
          showNow();
        }
      } catch (_) {
        // ignore network errors
      }
    };

    // Prime baseline then start interval
    const params = new URLSearchParams(window.location.search);
    const force = params.has('showUpdateToast') || params.has('forceUpdate');
    if (force) {
      // Defer slightly to ensure ToastContainer is mounted
      setTimeout(() => {
        try { console.info('[update-notifier] forced toast via URL param'); } catch { }
        showNow();
      }, 50);
    }
    check(force);
    timer = setInterval(check, Math.max(15000, intervalMs));

    // Dev helpers: expose a global and a query param to trigger the toast
    try {
      // window function to trigger manually
      // eslint-disable-next-line no-underscore-dangle
      window.__csvViewerShowUpdateToast = showNow;
      // param handled above
    } catch { }

    return () => {
      if (timer) clearInterval(timer);
      // Do not auto-dismiss on cleanup to avoid losing the toast in React StrictMode
    };
  }, [intervalMs]);
}
