import { useEffect, useRef, useState } from 'react';

/**
 * Polls backend indexing task status for progress meta.
 * Usage:
 * const { start, progress, status, error, reset } = useIndexingProgress();
 * start(taskId) after triggering /api/search/index/all or /rebuild.
 */
export default function useIndexingProgress(intervalMs = 2000) {
    const [taskId, setTaskId] = useState(null);
    const [status, setStatus] = useState('idle');
    const [progress, setProgress] = useState(null);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const timerRef = useRef(null);

    const clearTimer = () => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    };

    const poll = async (id) => {
        try {
            const resp = await fetch(`/api/search/index/status/${id}`);
            if (!resp.ok) throw new Error(`Status ${resp.status}`);
            const data = await resp.json();
            if (data.status === 'running') {
                setStatus('running');
                if (data.progress) setProgress(data.progress);
                timerRef.current = setTimeout(() => poll(id), intervalMs);
            } else if (data.status === 'completed') {
                setStatus('completed');
                setResult(data.result);
                setProgress(null);
            } else if (data.status === 'failed') {
                setStatus('failed');
                setError(data.error || 'Indexing failed');
            } else {
                // Unknown state -> keep polling a bit
                timerRef.current = setTimeout(() => poll(id), intervalMs);
            }
        } catch (e) {
            setError(e.message);
            setStatus('error');
        }
    };

    const start = (id, snapshot) => {
        clearTimer();
        setTaskId(id);
        setStatus('starting');
        setProgress(snapshot || null);
        setResult(null);
        setError(null);
        // If we have a real id (not placeholder) poll; otherwise just treat snapshot as running
        if (id && id !== 'unknown') {
            poll(id);
        } else if (snapshot) {
            setStatus('running');
        }
    };

    const reset = () => {
        clearTimer();
        setTaskId(null);
        setStatus('idle');
        setProgress(null);
        setResult(null);
        setError(null);
    };

    useEffect(() => () => clearTimer(), []);

    return { taskId, status, progress, result, error, start, reset };
}
