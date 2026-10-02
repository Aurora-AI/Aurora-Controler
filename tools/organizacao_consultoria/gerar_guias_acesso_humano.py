"""Gera os guias de navegação aprovados; não aprova conteúdo metodológico."""
from pathlib import Path
from html import escape
from urllib.parse import quote, unquote, urlparse
import hashlib, json, re
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[3] / 'ElysianConsult'
BASE = ROOT / 'Documentos e Manuais'
EVID = ROOT / 'docs/VALIDACAO' / ('guias_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
EVID.mkdir(parents=True)
STYLE = getSampleStyleSheet()
STYLE['Title'].textColor = colors.HexColor('#154c50')
STYLE['BodyText'].fontSize = 11
STYLE['BodyText'].leading = 16
CSS = 'body{font:18px/1.6 Segoe UI,Arial,sans-serif;max-width:960px;margin:50px auto;padding:0 24px;color:#233536;background:#f8faf9}h1,h2{color:#154c50}a{color:#12666b}li{margin:12px 0}.note{padding:16px;background:#fff3d6;border-left:4px solid #d39931}footer{margin-top:40px;font-size:14px}'
outputs = []

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    outputs.append(path)

def guide(rel, title, paragraphs):
    path = BASE / rel
    story = [Paragraph(escape(title), STYLE['Title']), Spacer(1,18)]
    for heading, text in paragraphs:
        story += [Paragraph(escape(heading), STYLE['Heading2']), Paragraph(escape(text), STYLE['BodyText']), Spacer(1,10)]
    story += [Spacer(1,12), Paragraph('Elysian Consult | Guia de orientação | 11/09/2026 | Uso interno', STYLE['Normal'])]
    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(path), rightMargin=45,leftMargin=45,topMargin=42,bottomMargin=42).build(story)
    outputs.append(path)
    doc = pdfium.PdfDocument(str(path))
    for i in range(len(doc)):
        page = doc[i]
        image = page.render(scale=1.1).to_pil()
        image.save(EVID / (path.stem + f'-{i+1}.png'))
        page.close()
    doc.close()

guide('Comece aqui.pdf','Comece aqui',[
 ('Onde ficam os documentos','Abra OneDrive > Consultoria > Documentos e Manuais. Para navegar por links, abra Comece aqui.html na mesma pasta. O local da pasta OneDrive pode variar conforme o computador de cada pessoa.'),
 ('Conhecer a empresa e os responsáveis','Abra Sobre a Consultoria. Rodrigo cuida de gestão, vendas, dados e ferramentas; Marcos lidera método óptico, relacionamento e aplicação em campo. Marketing é uma frente prevista, com responsável a definir.'),
 ('Consultar um método','Abra Métodos de Trabalho. Há uma área para Gestão e Vendas e outra para Óticas. Os materiais existentes são referências: a organização não equivale à aprovação de cada versão.'),
 ('Preparar um atendimento ou proposta','Abra Atendimento ao Cliente ou Comercial e Propostas. Consulte os avisos de pendência antes de usar um modelo ou prometer escopo, prazo ou preço.'),
 ('Encontrar regras e planilhas','Abra Indicadores e Regras de Cálculo ou Modelos e Planilhas. O acervo anterior de planilhas ainda precisa de classificação; não é um conjunto de modelos aprovados.'),
 ('Trabalhar em um cliente','Abra OneDrive > Consultoria > Clientes e Projetos. Copie a estrutura-modelo para Nome do Cliente > Nome do Projeto. Separe dados recebidos, análises em elaboração e relatórios entregues.'),
 ('O que é Aurora EXRS','É o software que processa os dados. Ele fica fora da pasta compartilhada. Você não precisa acessar o software ou os demais projetos para consultar estes documentos.')])
guide('Sobre a Consultoria/O que fazemos e para quem.pdf','O que fazemos e para quem',[
 ('Propósito','Organizar dados e processos da empresa cliente, produzir um diagnóstico e orientar a execução de um plano de ação pela consultoria.'),
 ('Primeira aplicação','O foco inicial é o ramo óptico, com o método de Marcos. Gestão, vendas, ferramentas e análise de dados formam a base reutilizável para outros setores.'),
 ('Situação dos materiais','O acervo está em consolidação. Método final, oferta, preços, modelos comerciais e critérios de entrega exigem decisões registradas dos responsáveis. Este guia não é uma proposta comercial.')])
guide('Sobre a Consultoria/Responsabilidades dos sócios.pdf','Responsabilidades dos sócios',[
 ('Rodrigo','Gestão administrativa, vendas, ferramentas, aplicações, dados e estudos aplicáveis a diferentes setores. Coordena a organização do acervo e a frente técnica.'),
 ('Marcos','Relacionamento no ramo óptico, método para óticas, aplicação de teorias e processos e trabalho de campo. Valida a aplicação do método óptico.'),
 ('Marketing','Frente prevista de posicionamento, aquisição e materiais comerciais. Pessoa responsável e composição societária ainda a definir.'),
 ('Demais participantes','Consultores de campo usam os procedimentos aprovados e registram evidências. Desenvolvedores mantêm o software Aurora EXRS. Estas funções não representam contratação ou atribuição já formalizada.')])
guide('Atendimento ao Cliente/Como iniciar um diagnóstico.pdf','Como iniciar um diagnóstico',[
 ('Guia de orientação em elaboração','Esta sequência organiza o trabalho. O procedimento definitivo de campo deve ser validado por Rodrigo e Marcos antes de ser adotado como método aprovado.'),
 ('1. Abrir o projeto','Em Clientes e Projetos, copie a estrutura-modelo para uma pasta identificada pelo cliente e pelo projeto. Registre responsável e objetivo.'),
 ('2. Confirmar o combinado','Guarde a proposta aceita e o contrato em Proposta e Contrato. Confirme empresas, lojas, período e escopo antes de receber ou interpretar os dados.'),
 ('3. Receber e conferir os dados','Guarde os arquivos originais em Dados Recebidos, sem sobrescrever reenvios. Registre fonte, período, loja e significado dos valores. Lacunas precisam ser esclarecidas.'),
 ('4. Analisar e revisar','Trabalhe em Análises em Elaboração. Rodrigo revisa os dados e Marcos revisa a aplicação óptica. Separe fatos comprovados, hipóteses e informações insuficientes.'),
 ('5. Entregar e acompanhar','Somente após revisão, coloque a versão entregue em Relatórios Entregues. Registre responsáveis e prazos no Plano de Ação, e medições posteriores em Acompanhamento e Resultados.')])
guide('Atendimento ao Cliente/Como solicitar os dados.pdf','Como solicitar os dados',[
 ('Preparação','Confirme com o responsável do cliente quais empresas, lojas e períodos serão analisados e onde os arquivos serão recebidos.'),
 ('Identificação dos arquivos','Peça a identificação do sistema de origem, data da exportação, empresa, loja, período e pessoa de contato. Preserve o arquivo original.'),
 ('Significado dos valores','Peça esclarecimento sobre preço unitário, total da linha, bruto, líquido, desconto, estorno e quantidade. Para estoque, identifique a data da posição, além da última movimentação.'),
 ('Conferência','Liste arquivos recebidos, ausentes e reenviados. Divergências entre planilhas e documentos fiscais precisam de revisão antes de apresentar números como definitivos.'),
 ('Situação','Orientação inicial para revisão de Rodrigo e Marcos. Modelos padronizados de coleta e checklist ainda não foram aprovados nesta reorganização.')])
guide('Comercial e Propostas/Serviços e limites de entrega.pdf','Serviços e limites de entrega',[
 ('Finalidade','A proposta deve descrever diagnóstico, plano de ação e acompanhamento efetivamente contratados, com responsabilidades e entregáveis claros.'),
 ('Materiais disponíveis','A pasta Apresentações existentes contém documentos e apresentação comercial do acervo. A presença nesta pasta não os torna propostas aprovadas para envio.'),
 ('Pendências','Oferta final, preço, prazo, capacidade de atendimento e modelo de proposta precisam ser consolidados pelos sócios. A pasta Modelos de proposta está reservada para esses documentos.'),
 ('Antes de enviar','Rodrigo e Marcos devem confirmar o escopo que pode ser entregue. Registre a versão aceita na pasta do projeto do cliente.')])
guide('Indicadores e Regras de Cálculo/Como consultar as regras.pdf','Como consultar as regras',[
 ('Onde começar','Abra Materiais de referência para consultar os documentos de fórmulas do acervo. Use o índice desta pasta para acessar os registros detalhados e as decisões sobre regras.'),
 ('O que conferir','Antes de usar um indicador, confirme nome, significado, fórmula, dados necessários, período, fonte e decisão vigente. Uma regra sem essas informações não deve virar conclusão automática.'),
 ('Quem esclarece','Rodrigo coordena cálculo e dados. Marcos valida a aplicação ao ramo óptico. Divergências devem ser registradas e resolvidas antes de usar o indicador numa entrega.')])

pending = {
 'Comercial e Propostas/Modelos de proposta':'Modelo comercial aprovado ainda não consolidado. Consulte Rodrigo e Marcos. Não há proposta pronta para envio nesta pasta.',
 'Atendimento ao Cliente/Checklists de visita':'Checklist aprovado de visita ainda não consolidado. Consulte o guia Como iniciar um diagnóstico e os materiais da equipe.',
 'Modelos e Planilhas':'As planilhas do Acervo anterior - classificação pendente são referências existentes, não modelos vazios aprovados. Não as use como dados de um novo cliente.',
}
for folder,text in pending.items():
    write(BASE/folder/'Leia antes de usar.txt',text+'\n')

sections = [
 ('Sobre a Consultoria','Conhecer a empresa e os responsáveis'),
 ('Métodos de Trabalho','Consultar métodos de gestão, vendas e óticas'),
 ('Atendimento ao Cliente','Preparar um diagnóstico e solicitar dados'),
 ('Comercial e Propostas','Consultar apresentações e preparar propostas'),
 ('Indicadores e Regras de Cálculo','Encontrar fontes e regras de cálculo'),
 ('Modelos e Planilhas','Consultar o acervo de planilhas'),
]
def html(title,body):
    return '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>'+CSS+'</style><body><h1>'+escape(title)+'</h1>'+body+'<footer>Elysian Consult · Uso interno · Organização de 11/09/2026. Novo teste de usabilidade pendente.</footer></body></html>'
published_sources = []
for source_name, label in [('DECISOES.md','Decisões sobre as regras'),('INVENTARIO.csv','Lista de fontes do catálogo'),('FILA_DECISAO.md','Regras que aguardam decisão')]:
    source = ROOT / 'docs/CATALOGO' / source_name
    target = BASE / 'Indicadores e Regras de Cálculo/Fontes e decisões para consulta' / (label + '.html')
    data = source.read_bytes()
    body = '<p class="note">Consulta gerada do registro oficial. Não editar esta cópia de leitura. Solicite alterações a Rodrigo. Atualizada em '+datetime.now().strftime('%d/%m/%Y %H:%M')+'.</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.6 Segoe UI,Arial">'+escape(data.decode('utf-8-sig'))+'</pre><a href="../%C3%8Dndice%20de%20documentos.html">Voltar às regras</a>'
    write(target,html(label,body))
    published_sources.append({'source':str(source),'sha256':hashlib.sha256(data).hexdigest(),'published':str(target)})
for rel, target in [
 ('Métodos de Trabalho/Manual para a equipe - versão existente.html','Manual Elysian e materiais da equipe/renders/ELYSIAN_EQUIPE_v1.docx'),
 ('Métodos de Trabalho/Óticas/Apresentação do Método 360 Óticas.html','Apresentações e estudos/360_Oticas_Apresentacao.pdf'),
 ('Métodos de Trabalho/Óticas/Método em linguagem simples - referência.html','../../Comercial e Propostas/Apresentações existentes/Oticas_Metodo_Linguagem_Simples.docx'),
 ('Sobre a Consultoria/Material para os sócios - versão existente.html','../Métodos de Trabalho/Manual Elysian e materiais da equipe/renders/ELYSIAN_SOCIOS_v1.docx')]:
    write(BASE/rel,html(Path(rel).stem,'<p><a href="'+quote(target)+'">Abrir documento</a></p><p>Material existente do acervo. Consulte sua versão e situação antes de usar.</p>'))
for folder,desc in sections:
    d = BASE/folder
    files = sorted(p for p in d.rglob('*') if p.is_file() and p.suffix not in {'.html','.lnk'})
    body = '<p>'+escape(desc)+'.</p><p class="note">Materiais do acervo: consulte a versão e a situação antes de usar. Esta organização não aprova conteúdos históricos.</p><ul>'
    for f in files:
        rel = f.relative_to(d).as_posix()
        body += '<li><a href="'+quote(rel)+'">'+escape(str(f.relative_to(d)))+'</a></li>'
    body += '</ul>'
    if folder == 'Indicadores e Regras de Cálculo':
        body += '<h2>Fontes detalhadas e decisões</h2><p>Consultas publicadas dos registros oficiais. Para alteração ou interpretação, consulte Rodrigo.</p><ul>'
        for label in ['Decisões sobre as regras','Lista de fontes do catálogo','Regras que aguardam decisão']:
            body += '<li><a href="'+quote('Fontes e decisões para consulta/'+label+'.html')+'">'+escape(label)+'</a></li>'
        body += '</ul>'
    body += '<p><a href="../Comece%20aqui.html">Voltar ao início</a></p>'
    write(d/'Índice de documentos.html', html(folder,body))
body = '<p>Escolha o que você precisa fazer. Todos os materiais de trabalho estão organizados aqui.</p><ul>'
for folder,desc in sections:
    body += '<li><a href="'+quote(folder+'/Índice de documentos.html')+'">'+escape(desc)+'</a><br><small>'+escape(folder)+'</small></li>'
body += '<li><a href="../Clientes%20e%20Projetos/Como%20organizar%20um%20projeto.txt">Organizar um cliente e um projeto</a></li></ul><p>Prefere imprimir? <a href="Comece%20aqui.pdf">Abra o guia em PDF</a>.</p><p class="note">As pastas de modelos indicam o que ainda está pendente. O acervo não deve ser tratado como material aprovado para envio ao cliente.</p>'
write(BASE/'Comece aqui.html',html('Documentos e Manuais',body))
write(ROOT/'Clientes e Projetos/Como organizar um projeto.txt','Crie Nome do Cliente / Nome do Projeto e copie as seis pastas do modelo.\nOs originais recebidos ficam em Dados Recebidos; preserve cada reenvio.\nAnálises em Elaboração não são entregas aprovadas. Somente versões revisadas e efetivamente entregues ficam em Relatórios Entregues.\nNão há clientes criados ou dados reais movidos para esta área nesta reorganização.\nO direcionamento automático de saídas do software para estas pastas ainda depende de integração técnica; por enquanto o responsável do projeto deve salvar as entregas aqui.\n')

# Verifica links locais reais dos índices, sem depender de aprovação de conteúdo.
checks=[]
for page in (p for p in outputs if p.suffix=='.html'):
    for href in re.findall(r'href="([^"]+)"',page.read_text(encoding='utf-8')):
        target = (page.parent/unquote(href)).resolve()
        if not target.exists(): raise RuntimeError(f'Link ausente: {page} -> {href}')
        if not target.is_relative_to(BASE.resolve().parent):
            raise RuntimeError(f'Link fora da pasta de publicação: {page} -> {href}')
        checks.append({'page':str(page),'target':str(target)})
manifest=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in outputs]
(EVID/'guias_e_links.json').write_text(json.dumps({'outputs':manifest,'links':checks,'published_sources':published_sources,'human_acceptance':'pendente'},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'GUIAS_OK: {len(outputs)} arquivos gerados; {len(checks)} links locais válidos. PDFs renderizados para inspeção.')
