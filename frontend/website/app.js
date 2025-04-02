document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('root');

    fetch('http://localhost:8000/narratives')  // Update to EC2 IP post-deployment
        .then(response => response.json())
        .then(narratives => {
            narratives.forEach(narrative => {
                const div = document.createElement('div');
                div.className = 'narrative-card';
                const articles = JSON.parse(narrative.articles).map(a => `${a.source}: ${a.url}`).join('<br>');
                div.innerHTML = `
                    <h2>${narrative.title}</h2>
                    <p><strong>Summary:</strong> ${narrative.summary}</p>
                    <p><strong>Left Angle:</strong> ${narrative.left_angle}</p>
                    <p><strong>Right Angle:</strong> ${narrative.right_angle}</p>
                    <p><strong>Articles:</strong><br>${articles}</p>
                `;
                root.appendChild(div);
            });
        });
});