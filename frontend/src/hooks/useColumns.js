import { useState, useEffect } from 'react';
import axios from 'axios';

/**
 * Hook to fetch available columns from the backend
 * @returns {Object} { columns, loading, error, refreshColumns }
 */
const useColumns = () => {
    const [columns, setColumns] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchColumns = async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await axios.get('/api/files/columns');

            if (response.data.success) {
                setColumns(response.data.columns);
            } else {
                throw new Error(response.data.message || 'Failed to fetch columns');
            }
        } catch (err) {
            console.error('Error fetching columns:', err);
            setError(err.message || 'Failed to fetch available columns');

            // Fallback to empty array if API fails
            setColumns([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchColumns();
    }, []);

    const refreshColumns = () => {
        fetchColumns();
    };

    return {
        columns,
        loading,
        error,
        refreshColumns
    };
};

export default useColumns;
