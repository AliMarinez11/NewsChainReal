document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('root');

    fetch('/clusters')
        .then(response => response.json())
        .then(clusters => {
            clusters.forEach(cluster => {
                const div = document.createElement('div');
                div.className = 'cluster';
                div.innerHTML = `
                    <h2>Cluster ${cluster.cluster_id} (${cluster.size} articles)</h2>
                    <ul>
                        ${cluster.sample.map(s => `<li>${s.title} (${s.source}, ${s.pub_date}, ${s.topic})</li>`).join('')}
                    </ul>
                    <button onclick="validate(${cluster.cluster_id}, true)">Valid</button>
                    <button onclick="validate(${cluster.cluster_id}, false)">Invalid</button>
                `;
                root.appendChild(div);
            });
        });

    window.validate = (cluster_id, is_valid) => {
        fetch('/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cluster_id, is_valid })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(`Cluster ${cluster_id} marked as ${is_valid ? 'valid' : 'invalid'}`);
            }
        });
    };
});