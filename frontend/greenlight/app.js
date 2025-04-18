document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('root');
    const executionSelect = document.createElement('select');
    executionSelect.id = 'executionSelect';
    executionSelect.innerHTML = '<option value="">Select Execution ID</option>';
    root.appendChild(executionSelect);

    const errorDiv = document.createElement('div');
    errorDiv.id = 'error';
    errorDiv.style.color = 'red';
    root.appendChild(errorDiv);

    const clustersDiv = document.createElement('div');
    clustersDiv.id = 'clusters';
    root.appendChild(clustersDiv);

    // Fetch available execution IDs
    fetch('/executions')
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch executions');
            return response.json();
        })
        .then(executions => {
            executions.forEach(execution => {
                const option = document.createElement('option');
                option.value = execution;
                option.textContent = execution;
                executionSelect.appendChild(option);
            });
        })
        .catch(error => {
            errorDiv.textContent = error.message;
        });

    // Fetch clusters when an execution ID is selected
    executionSelect.addEventListener('change', async () => {
        const executionId = executionSelect.value;
        if (!executionId) {
            clustersDiv.innerHTML = '';
            return;
        }

        errorDiv.textContent = '';
        try {
            // Call /previous_validations to perform inheritance
            const prevResponse = await fetch(`/previous_validations?execution_id=${encodeURIComponent(executionId)}`);
            if (!prevResponse.ok) throw new Error('Failed to fetch previous validations');
            const prevData = await prevResponse.json();
            console.log('Previous validations:', prevData); // Debug log

            // Then fetch clusters
            const response = await fetch(`/clusters?execution_id=${encodeURIComponent(executionId)}`);
            if (!response.ok) throw new Error('Failed to fetch clusters');
            const clusters = await response.json();
            clustersDiv.innerHTML = '';
            clusters.forEach(cluster => {
                const div = document.createElement('div');
                div.className = 'cluster';
                div.innerHTML = `
                    <h2>Cluster ${cluster.cluster_id} (${cluster.size} articles)</h2>
                    <p>Status: ${cluster.status || 'Not Reviewed'}</p>
                    <ul>
                        ${cluster.sample.map(s => `<li>${s.title} (${s.source})</li>`).join('')}
                    </ul>
                    <button onclick="validate('${executionId}', ${cluster.cluster_id}, true)">Valid</button>
                    <button onclick="validate('${executionId}', ${cluster.cluster_id}, false)">Not Valid</button>
                `;
                clustersDiv.appendChild(div);
            });
        } catch (error) {
            errorDiv.textContent = error.message;
        }
    });

    window.validate = (executionId, clusterId, isValid) => {
        fetch('/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ execution_id: executionId, cluster_id: clusterId, is_valid: isValid })
        })
        .then(response => {
            if (!response.ok) throw new Error('Failed to validate cluster');
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                alert(`Cluster ${clusterId} marked as ${isValid ? 'valid' : 'invalid'}`);
                // Refresh clusters
                executionSelect.dispatchEvent(new Event('change'));
            }
        })
        .catch(error => {
            errorDiv.textContent = error.message;
        });
    };
});