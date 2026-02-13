/**
 * Knowledge Graph – vis.js network visualisation
 */
document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('graphCanvas');
    if (!container) return;

    fetch('/api/graph-data')
        .then(function (r) { return r.json(); })
        .then(function (data) { renderGraph(container, data); })
        .catch(function (err) {
            console.error('Graph load error:', err);
            container.innerHTML = '<div class="empty-state"><p>Failed to load graph data.</p></div>';
        });
});

function renderGraph(container, data) {
    var nodes = new vis.DataSet(data.nodes);
    var edges = new vis.DataSet(data.edges);

    var options = {
        nodes: {
            font: { size: 12, face: 'Inter, sans-serif' },
            borderWidth: 2,
            shadow: { enabled: true, color: 'rgba(0,0,0,0.06)', size: 6, x: 0, y: 2 }
        },
        edges: {
            font: { size: 10, face: 'Inter, sans-serif', color: '#6b6b76', strokeWidth: 0 },
            smooth: { enabled: true, type: 'continuous', roundness: 0.5 },
            arrows: { to: { enabled: true, scaleFactor: 0.5 } }
        },
        physics: {
            enabled: true,
            barnesHut: {
                gravitationalConstant: -8000,
                centralGravity: 0.3,
                springLength: 150,
                springConstant: 0.04,
                damping: 0.09,
                avoidOverlap: 0.5
            },
            stabilization: { enabled: true, iterations: 200 }
        },
        interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true }
    };

    var network = new vis.Network(container, { nodes: nodes, edges: edges }, options);

    network.on('stabilizationIterationsDone', function () {
        network.setOptions({ physics: { enabled: false } });
    });

    // Edge click: show explanation popup
    network.on('click', function (params) {
        var existing = document.getElementById('edgePopup');
        if (existing) existing.remove();

        if (params.edges.length === 1 && params.nodes.length === 0) {
            var edgeId = params.edges[0];
            var edge = edges.get(edgeId);
            if (edge && edge.title) {
                var popup = document.createElement('div');
                popup.id = 'edgePopup';
                popup.className = 'edge-popup';
                popup.style.left = params.event.center.x + 'px';
                popup.style.top = params.event.center.y + 'px';
                popup.innerHTML = '<div class="card-label">Connection</div>'
                    + '<div class="edge-popup-relationship">' + (edge.label || '') + '</div>'
                    + '<div class="edge-popup-explanation">' + edge.title + '</div>'
                    + '<div class="edge-popup-close"><button class="btn btn-sm" onclick="document.getElementById(\'edgePopup\').remove()" style="background:var(--bg-primary);color:var(--text-secondary);box-shadow:none;">Close</button></div>';
                container.style.position = 'relative';
                container.appendChild(popup);
            }
        }
    });
}
