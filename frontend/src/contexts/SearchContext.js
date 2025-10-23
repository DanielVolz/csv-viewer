import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'csv-viewer.search-state.v1';

const defaultPagination = Object.freeze({
    page: 1,
    pageSize: 100,
    totalItems: 0,
    totalPages: 0
});

const createDefaultState = () => ({
    searchTerm: '',
    includeHistorical: false,
    hasSearched: false,
    rawResults: null,
    pagination: { ...defaultPagination },
    lastQuery: null,
    lastUpdated: null
});

const loadPersistedState = () => {
    if (typeof window === 'undefined') {
        return createDefaultState();
    }
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return createDefaultState();
        }
        const parsed = JSON.parse(raw);
        return {
            ...createDefaultState(),
            ...parsed,
            pagination: { ...defaultPagination, ...(parsed?.pagination || {}) }
        };
    } catch (error) {
        console.warn('Failed to load persisted search state', error);
        return createDefaultState();
    }
};

const SearchContext = createContext(null);

export function SearchProvider({ children }) {
    const [persisted, setPersisted] = useState(() => loadPersistedState());
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
        } catch (storageError) {
            console.warn('Failed to persist search state', storageError);
        }
    }, [persisted]);

    const setSearchTerm = useCallback((value) => {
        setPersisted((prev) => ({
            ...prev,
            searchTerm: value ?? ''
        }));
    }, []);

    const setIncludeHistorical = useCallback((value) => {
        setPersisted((prev) => ({
            ...prev,
            includeHistorical: Boolean(value)
        }));
    }, []);

    const setHasSearched = useCallback((value) => {
        setPersisted((prev) => ({
            ...prev,
            hasSearched: Boolean(value)
        }));
    }, []);

    const setPaginationState = useCallback((updater) => {
        setPersisted((prev) => {
            const previous = prev.pagination || defaultPagination;
            const next = typeof updater === 'function'
                ? updater({ ...previous })
                : updater;
            const resolved = next || {};
            return {
                ...prev,
                pagination: { ...previous, ...resolved }
            };
        });
    }, []);

    const setRawResults = useCallback((value) => {
        setPersisted((prev) => ({
            ...prev,
            rawResults: value,
            lastUpdated: value ? Date.now() : null
        }));
    }, []);

    const setLastQuery = useCallback((value) => {
        setPersisted((prev) => ({
            ...prev,
            lastQuery: value ?? null
        }));
    }, []);

    const resetSearchState = useCallback(() => {
        const next = createDefaultState();
        setPersisted(next);
        setLoading(false);
        setError(null);
    }, []);

    const contextValue = useMemo(() => ({
        searchTerm: persisted.searchTerm,
        setSearchTerm,
        includeHistorical: persisted.includeHistorical,
        setIncludeHistorical,
        hasSearched: persisted.hasSearched,
        setHasSearched,
        pagination: persisted.pagination,
        setPaginationState,
        rawResults: persisted.rawResults,
        setRawResults,
        lastQuery: persisted.lastQuery,
        setLastQuery,
        lastUpdated: persisted.lastUpdated,
        loading,
        setLoading,
        error,
        setError,
        resetSearchState
    }), [persisted, setSearchTerm, setIncludeHistorical, setHasSearched, setPaginationState, setRawResults, setLastQuery, loading, error, resetSearchState]);

    return (
        <SearchContext.Provider value={contextValue}>
            {children}
        </SearchContext.Provider>
    );
}

export function useSearchContext() {
    const ctx = useContext(SearchContext);
    if (!ctx) {
        throw new Error('useSearchContext must be used within a SearchProvider');
    }
    return ctx;
}
