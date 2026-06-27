// Aurora Controler SPA Client Logic

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const pipelineSection = document.getElementById('pipelineSection');
    const resultsSection = document.getElementById('resultsSection');
    const pipelineMainStatus = document.getElementById('pipelineMainStatus');
    
    // Tab Buttons & Panels
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Table Pagination State
    let fullDataset = [];
    let tableColumns = [];
    let currentPage = 1;
    const rowsPerPage = 15;
    
    // Setup Tab Navigation
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const targetTab = btn.getAttribute('data-tab');
            document.getElementById(targetTab).classList.add('active');
        });
    });

    // Drag and Drop Events
    dropzone.addEventListener('click', () => fileInput.click());
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
    
    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Reset Stepper UI
    function resetStepper() {
        const steps = ['A0', 'A1', 'A3', 'C0', 'C1-C3'];
        steps.forEach(id => {
            const el = document.getElementById(`step-${id}`);
            el.className = 'step';
            el.querySelector('.step-icon').innerHTML = '<i class="fa-solid fa-circle"></i>';
        });
        pipelineMainStatus.textContent = 'INICIANDO...';
        pipelineMainStatus.style.color = 'var(--text-muted)';
    }

    // Animate Stepper
    async function animateSteps(success = true) {
        const steps = [
            { id: 'A0', duration: 400 },
            { id: 'A1', duration: 500 },
            { id: 'A3', duration: 400 },
            { id: 'C0', duration: 500 },
            { id: 'C1-C3', duration: 600 }
        ];

        pipelineMainStatus.textContent = 'CONSTRUINDO AST & DEPENDÊNCIAS...';
        pipelineMainStatus.style.color = 'var(--primary-light)';

        for (let i = 0; i < steps.length; i++) {
            const step = steps[i];
            const el = document.getElementById(`step-${step.id}`);
            
            // Set Active
            el.classList.add('active');
            el.querySelector('.step-icon').innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
            
            await new Promise(resolve => setTimeout(resolve, step.duration));
            
            // Set Success or Error (last step can be fail if something goes wrong, but usually succeeds)
            el.classList.remove('active');
            if (success || i < steps.length - 1) {
                el.classList.add('success');
                el.querySelector('.step-icon').innerHTML = '<i class="fa-solid fa-circle-check"></i>';
            } else {
                el.classList.add('error');
                el.querySelector('.step-icon').innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
            }
        }
        
        if (success) {
            pipelineMainStatus.textContent = 'COMPILAÇÃO CONCLUÍDA';
            pipelineMainStatus.style.color = 'var(--success)';
        } else {
            pipelineMainStatus.textContent = 'FALHA NA COMPILAÇÃO';
            pipelineMainStatus.style.color = 'var(--danger)';
        }
    }

    // Handle Upload & Process
    async function handleFileUpload(file) {
        resetStepper();
        pipelineSection.style.display = 'block';
        resultsSection.style.display = 'none';
        
        // Scroll to pipeline section
        pipelineSection.scrollIntoView({ behavior: 'smooth' });
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // Start the stepper animation concurrently with the request
            const animationPromise = animateSteps(true);
            
            const response = await fetch('/api/v1/dashboard/upload-and-generate', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Erro ao processar arquivo.');
            }
            
            const data = await response.json();
            
            // Wait for visual animations to finish to guarantee amazing user experience
            await animationPromise;
            
            // Render the results!
            renderResults(data);
            
            // Show results section
            resultsSection.style.display = 'block';
            setTimeout(() => {
                resultsSection.scrollIntoView({ behavior: 'smooth' });
            }, 100);
            
        } catch (error) {
            console.error(error);
            pipelineMainStatus.textContent = `ERRO: ${error.message}`;
            pipelineMainStatus.style.color = 'var(--danger)';
            // Mark last active step as error
            const activeStep = document.querySelector('.step.active');
            if (activeStep) {
                activeStep.className = 'step error';
                activeStep.querySelector('.step-icon').innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
            }
            alert(`Falha no processamento: ${error.message}`);
        }
    }

    // Render Results
    function renderResults(data) {
        const { c0_dataset, spec } = data;
        
        // 1. Title and Narrative
        document.getElementById('renderedDashboardTitle').textContent = spec.title || 'Dashboard Gerado';
        
        const narrativeBox = document.getElementById('narrativeBox');
        if (spec.narrative && spec.narrative.length > 0) {
            narrativeBox.style.display = 'block';
            document.getElementById('narrativeContent').textContent = spec.narrative.map(n => n.text).join('\n\n');
        } else {
            narrativeBox.style.display = 'none';
        }
        
        // 2. Render KPI cards
        renderKPIs(spec);
        
        // 3. Render Charts Bento Grid
        renderChartsGrid(spec);
        
        // 4. Render Ingested Data C0 Tab
        setupDatasetTab(c0_dataset);
        
        // 5. Render Raw Spec JSON Tab
        const codeElement = document.getElementById('jsonPreCode');
        codeElement.textContent = JSON.stringify(spec, null, 2);
        
        // Setup copy button
        const copyBtn = document.getElementById('copyJsonBtn');
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(codeElement.textContent).then(() => {
                copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copiado!';
                setTimeout(() => {
                    copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copiar';
                }, 2000);
            });
        });
    }

    // Render KPIs helper
    function renderKPIs(spec) {
        const kpisContainer = document.getElementById('kpisContainer');
        kpisContainer.innerHTML = '';
        
        // Find KPI components in spec
        const kpiComponents = spec.components.filter(c => c.type === 'kpi_cards');
        
        if (kpiComponents.length === 0) {
            kpisContainer.style.display = 'none';
            return;
        }
        
        kpisContainer.style.display = 'grid';
        
        kpiComponents.forEach(comp => {
            const dataView = spec.data_views[comp.data_binding];
            if (!dataView || !dataView.rows) return;
            
            dataView.rows.forEach(row => {
                const card = document.createElement('div');
                card.className = 'kpi-card';
                
                const label = document.createElement('div');
                label.className = 'kpi-label';
                label.textContent = row.label || row.metric || 'Métrica';
                
                const value = document.createElement('div');
                value.className = 'kpi-value';
                
                // Format values beautifully
                const rawVal = parseFloat(row.value);
                if (isNaN(rawVal)) {
                    value.textContent = row.value;
                } else if (row.metric && (row.metric.includes('taxa') || row.metric.includes('percentual') || row.metric.includes('ratio') || row.metric.includes('conversao'))) {
                    value.textContent = (rawVal * 100).toFixed(1) + '%';
                } else if (rawVal > 1000000) {
                    value.textContent = (rawVal / 1000000).toFixed(1) + 'M';
                } else if (rawVal > 1000) {
                    value.textContent = rawVal.toLocaleString('pt-BR');
                } else {
                    value.textContent = rawVal.toFixed(1).replace('.0', '');
                }
                
                const desc = document.createElement('div');
                desc.className = 'kpi-desc';
                desc.textContent = comp.analytical_intent || `Fórmula: ${row.formula || ''}`;
                
                card.appendChild(label);
                card.appendChild(value);
                card.appendChild(desc);
                kpisContainer.appendChild(card);
            });
        });
    }

    // Render Charts Bento Grid helper
    function renderChartsGrid(spec) {
        const chartsContainer = document.getElementById('chartsContainer');
        chartsContainer.innerHTML = '';
        
        // Filter out components that are NOT kpis
        const chartComponents = spec.components.filter(c => c.type !== 'kpi_cards');
        
        if (chartComponents.length === 0) {
            chartsContainer.style.display = 'none';
            return;
        }
        
        chartsContainer.style.display = 'grid';
        
        // If layout configuration exists, use it to allocate grid spaces, else balance them
        const layoutRows = (spec.layout && spec.layout.rows) ? spec.layout.rows : [];
        const layoutFlattened = layoutRows.flat();
        
        chartComponents.forEach(comp => {
            const dataView = spec.data_views[comp.data_binding];
            if (!dataView || !dataView.rows || dataView.rows.length === 0) return;
            
            // Build card container
            const card = document.createElement('div');
            card.className = 'chart-card';
            
            // Dynamic column layout based on layout rows or heuristics
            let colSpan = 6; // default half width
            if (layoutFlattened.includes(comp.id)) {
                // Find row containing it
                const row = layoutRows.find(r => r.includes(comp.id));
                if (row) {
                    colSpan = Math.floor(12 / row.length);
                }
            } else if (comp.type === 'heatmap' || dataView.rows.length > 15) {
                colSpan = 12; // full width
            }
            card.classList.add(`col-${colSpan}`);
            
            // Header
            const header = document.createElement('div');
            header.className = 'chart-card-header';
            
            const title = document.createElement('span');
            title.className = 'chart-card-title';
            title.textContent = comp.analytical_intent || `Visualização ${comp.id}`;
            
            header.appendChild(title);
            card.appendChild(header);
            
            // Chart Body Container
            const chartBody = document.createElement('div');
            chartBody.className = 'chart-body';
            chartBody.id = `chart-el-${comp.id}`;
            card.appendChild(chartBody);
            
            chartsContainer.appendChild(card);
            
            // Render the specific ApexChart!
            renderApexChart(comp, dataView);
        });
    }

    // Helper: Map data_view rows into ApexCharts series and categories
    function renderApexChart(component, dataView) {
        const selector = `#chart-el-${component.id}`;
        const container = document.querySelector(selector);
        if (!container) return;
        
        const type = component.type;
        const rows = dataView.rows;
        const cols = dataView.columns;
        
        // Find dimension column (usually first string column) and measures (numerical columns)
        let dimCol = cols[0];
        let valCols = cols.slice(1);
        
        // Categories/Labels
        const categories = rows.map(r => String(r[dimCol] !== undefined ? r[dimCol] : ''));
        
        // ApexChart Options skeleton
        let options = {
            chart: {
                height: 320,
                background: 'transparent',
                foreColor: '#9ca3af',
                fontFamily: 'var(--font-sans)',
                toolbar: { show: false }
            },
            theme: { mode: 'dark' },
            colors: ['#7c3aed', '#06b6d4', '#10b981', '#f59e0b', '#ef4444'],
            stroke: { width: 3, curve: 'smooth' },
            grid: {
                borderColor: 'rgba(255,255,255,0.06)',
                xaxis: { lines: { show: false } },
                yaxis: { lines: { show: true } }
            },
            xaxis: {
                categories: categories,
                axisBorder: { show: false },
                axisTicks: { show: false }
            },
            tooltip: {
                theme: 'dark',
                y: {
                    formatter: function(val) {
                        return typeof val === 'number' ? val.toLocaleString('pt-BR') : val;
                    }
                }
            }
        };
        
        // Customize options by Chart Type
        if (type === 'line') {
            options.chart.type = 'line';
            options.series = valCols.map(col => ({
                name: col,
                data: rows.map(r => parseFloat(r[col]) || 0)
            }));
        } else if (type === 'bar_ranking' || type === 'horizontal_bar') {
            options.chart.type = 'bar';
            options.plotOptions = {
                bar: {
                    horizontal: true,
                    borderRadius: 4,
                    barHeight: '65%'
                }
            };
            options.series = valCols.map(col => ({
                name: col,
                data: rows.map(r => parseFloat(r[col]) || 0)
            }));
            // swap categories to yaxis
            delete options.xaxis.categories;
            options.yaxis = { categories: categories };
        } else if (type === 'stacked_bar') {
            options.chart.type = 'bar';
            options.chart.stacked = true;
            options.plotOptions = {
                bar: {
                    horizontal: false,
                    borderRadius: 4
                }
            };
            options.series = valCols.map(col => ({
                name: col,
                data: rows.map(r => parseFloat(r[col]) || 0)
            }));
        } else if (type === 'kpi_cards') {
            // shouldn't reach here
            return;
        } else {
            // Fallback to simple column bar chart
            options.chart.type = 'bar';
            options.plotOptions = {
                bar: {
                    horizontal: false,
                    borderRadius: 4,
                    columnWidth: '50%'
                }
            };
            options.series = valCols.map(col => ({
                name: col,
                data: rows.map(r => parseFloat(r[col]) || 0)
            }));
        }
        
        // Render
        const chart = new ApexCharts(container, options);
        chart.render();
    }

    // Dataset Tab setup (C0 Tab)
    function setupDatasetTab(c0) {
        fullDataset = c0.dataset || [];
        
        // Metadata
        document.getElementById('detectedStructureText').innerHTML = `
            <strong>Layout:</strong> ${c0.detected_structure.table_kind} <br/>
            <strong>Dimensão Canonizada:</strong> ${c0.detected_structure.canonical_dimension_from_columns || 'N/A'} <br/>
            <strong>Medida Canonizada:</strong> ${c0.detected_structure.canonical_measure || 'N/A'}
        `;
        document.getElementById('rowsCountBadge').textContent = `${c0.validation_summary.dataset_rows_emitted} linhas geradas`;
        document.getElementById('strategyBadge').textContent = `Estratégia: ${c0.ingestion_strategy.used}`;
        
        // Extract headers from first dataset row keys
        if (fullDataset.length > 0) {
            tableColumns = Object.keys(fullDataset[0]).filter(k => k !== 'row_id');
        } else {
            tableColumns = [];
        }
        
        currentPage = 1;
        renderTablePage();
        
        // Pagination Event Listeners
        const prevPageBtn = document.getElementById('prevPageBtn');
        const nextPageBtn = document.getElementById('nextPageBtn');
        
        prevPageBtn.onclick = () => {
            if (currentPage > 1) {
                currentPage--;
                renderTablePage();
            }
        };
        
        nextPageBtn.onclick = () => {
            const maxPage = Math.ceil(fullDataset.length / rowsPerPage);
            if (currentPage < maxPage) {
                currentPage++;
                renderTablePage();
            }
        };
    }

    // Render Paginated Table Page
    function renderTablePage() {
        const headerRow = document.getElementById('datasetTableHeader');
        const bodyContainer = document.getElementById('datasetTableBody');
        const pageIndicator = document.getElementById('pageIndicator');
        const prevPageBtn = document.getElementById('prevPageBtn');
        const nextPageBtn = document.getElementById('nextPageBtn');
        
        headerRow.innerHTML = '';
        bodyContainer.innerHTML = '';
        
        if (fullDataset.length === 0) {
            headerRow.innerHTML = '<th>Nenhum dado</th>';
            bodyContainer.innerHTML = '<tr><td>Faça upload de uma planilha para visualizar os dados un-pivoted.</td></tr>';
            pageIndicator.textContent = 'Página 0 de 0';
            prevPageBtn.disabled = true;
            nextPageBtn.disabled = true;
            return;
        }
        
        // 1. Header
        // Add row ID first
        const idTh = document.createElement('th');
        idTh.textContent = 'Row ID';
        headerRow.appendChild(idTh);
        
        tableColumns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            headerRow.appendChild(th);
        });
        
        // 2. Paginated rows
        const start = (currentPage - 1) * rowsPerPage;
        const end = Math.min(start + rowsPerPage, fullDataset.length);
        const pageData = fullDataset.slice(start, end);
        
        pageData.forEach(row => {
            const tr = document.createElement('tr');
            
            // row_id
            const idTd = document.createElement('td');
            idTd.textContent = row.row_id;
            tr.appendChild(idTd);
            
            tableColumns.forEach(col => {
                const td = document.createElement('td');
                const val = row[col];
                
                if (typeof val === 'number') {
                    td.textContent = val.toLocaleString('pt-BR');
                    td.style.textAlign = 'right';
                } else if (val === null || val === undefined) {
                    td.textContent = '-';
                    td.style.fontStyle = 'italic';
                } else {
                    td.textContent = String(val);
                }
                
                tr.appendChild(td);
            });
            bodyContainer.appendChild(tr);
        });
        
        // 3. Update buttons
        const maxPage = Math.ceil(fullDataset.length / rowsPerPage);
        pageIndicator.textContent = `Página ${currentPage} de ${maxPage}`;
        prevPageBtn.disabled = currentPage === 1;
        nextPageBtn.disabled = currentPage === maxPage;
    }
});
