"""
Reconstrucao do ambiente de teste sintetico do GLPI SQL AI.

Remove TODOS os dados reais (chamados, base de conhecimento, seguidores, solucoes)
e repopula o banco com dados ficticios realistas, modelados nos campos usados em
chamados reais. Tambem anonimiza usuarios e nomes de referencia (setores, categorias,
grupos) para que nenhum dado pessoal/organizacional real permaneca no banco.

Uso:
    poetry run python scripts/rebuild_synthetic_data.py

Depois, reindexe a base vetorial e rode os testes.
"""

import os
import random
import sys
from datetime import datetime, timedelta

import mysql.connector
from dotenv import load_dotenv

random.seed(42)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB = dict(host=os.getenv("DB_HOST", "localhost"), database=os.getenv("DB_NAME", "glpidb"),
          user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""),
          connection_timeout=10)

NOW = datetime.now()


def log(*a):
    print(*a, flush=True)


def rebuild():
    cn = mysql.connector.connect(**DB)
    c = cn.cursor()
    c.execute("SET FOREIGN_KEY_CHECKS=0")

    # ---------------------------------------------------------------
    # 1. LIMPEZA dos dados reais (chamados + KB + conteudo textual real)
    # ---------------------------------------------------------------
    truncate = [
        "glpi_tickets", "glpi_tickets_users", "glpi_groups_tickets",
        "glpi_itilfollowups", "glpi_itilsolutions", "glpi_tickettasks",
        "glpi_ticketvalidations", "glpi_knowbaseitems",
        "glpi_knowbaseitems_profiles", "glpi_knowbaseitems_users",
    ]
    for t in truncate:
        try:
            c.execute(f"TRUNCATE TABLE {t}")
            log(f"  TRUNCATE {t}")
        except Exception as e:
            log(f"  (skip {t}: {e})")
    for t in ["glpi_knowbaseitemtranslations", "glpi_knowbaseitems_comments",
              "glpi_knowbaseitems_revisions"]:
        try:
            c.execute(f"TRUNCATE TABLE {t}")
        except Exception:
            pass
    try:
        c.execute("DELETE FROM glpi_documents_items WHERE itemtype IN ('Ticket','KnowbaseItem')")
    except Exception:
        pass

    # ---------------------------------------------------------------
    # 2. ANONIMIZACAO de usuarios e nomes de referencia
    # ---------------------------------------------------------------
    # Usuarios reais (id>=8) -> nomes genericos anonimizados
    c.execute("UPDATE glpi_users SET firstname='Colaborador', realname=CONCAT('Anonimo ', id) "
              "WHERE id >= 8")
    # Conjunto curado de pessoas ficticias (tecnicos e solicitantes)
    people = {
        10: ("Ana", "Pereira"), 11: ("Bruno", "Almeida"), 12: ("Carla", "Mendes"),
        13: ("Diego", "Rocha"), 14: ("Elaine", "Costa"), 15: ("Fabio", "Lima"),
        8: ("Gabriela", "Nunes"), 9: ("Henrique", "Dias"), 17: ("Isabela", "Ramos"),
        18: ("Joao", "Martins"), 19: ("Karina", "Souza"),
    }
    for uid, (fn, ln) in people.items():
        c.execute("UPDATE glpi_users SET firstname=%s, realname=%s WHERE id=%s", (fn, ln, uid))

    # Referencia que aparece nas saidas -> anonimiza tudo, nomeia o que sera usado
    c.execute("UPDATE glpi_itilcategories SET name=CONCAT('Categoria ', id), "
              "completename=CONCAT('Categoria ', id)")
    c.execute("UPDATE glpi_locations SET name=CONCAT('Setor ', id), "
              "completename=CONCAT('Setor ', id)")
    c.execute("UPDATE glpi_groups SET name=CONCAT('Grupo ', id)")
    c.execute("UPDATE glpi_entities SET name=CONCAT('Entidade ', id) WHERE id > 1")

    cats = {57: "Hardware", 52: "Acesso e Login", 58: "Rede", 54: "E-mail",
            50: "Acesso Remoto", 56: "Telefonia", 51: "Certificado Digital", 53: "Software"}
    locs = {6: "Apoio", 9: "Cadastro", 4: "Almoxarifado", 2: "Administracao",
            7: "Atendimento", 8: "Auditoria", 3: "Financeiro", 5: "Recepcao"}
    for cid, nm in cats.items():
        c.execute("UPDATE glpi_itilcategories SET name=%s, completename=%s WHERE id=%s", (nm, nm, cid))
    for lid, nm in locs.items():
        c.execute("UPDATE glpi_locations SET name=%s, completename=%s WHERE id=%s", (nm, nm, lid))
    c.execute("UPDATE glpi_entities SET name='TI', completename='TI' WHERE id=1")

    # valida ids de referencia existentes
    def existing(table, ids):
        c.execute(f"SELECT id FROM {table} WHERE id IN ({','.join(map(str, ids))})")
        return {r[0] for r in c.fetchall()}
    cat_ids = existing("glpi_itilcategories", cats)
    loc_ids = existing("glpi_locations", locs)
    usr_ids = existing("glpi_users", people)
    log(f"  refs validas: cat={len(cat_ids)} loc={len(loc_ids)} user={len(usr_ids)}")

    cur_year = NOW.year

    # ---------------------------------------------------------------
    # 3. GERACAO de chamados ficticios (entity 1)
    # ---------------------------------------------------------------
    techs = [10, 11, 12, 13, 14]           # tecnicos ficticios
    reqs = [8, 9, 15, 17, 18, 19]          # solicitantes ficticios
    techs = [u for u in techs if u in usr_ids]
    reqs = [u for u in reqs if u in usr_ids]

    def insert_ticket(tid, name, content, status, prio, urg, imp, cat, loc,
                      req, tech, days_ago, atrasado=False):
        dc = NOW - timedelta(days=days_ago, hours=random.randint(0, 8))
        dcs = dc.strftime("%Y-%m-%d %H:%M:%S")
        dms = (dc + timedelta(hours=max(1, days_ago))).strftime("%Y-%m-%d %H:%M:%S")
        solvedate = closedate = None
        if status in (5, 6):
            sd = dc + timedelta(days=max(1, days_ago // 2))
            solvedate = sd.strftime("%Y-%m-%d %H:%M:%S")
            if status == 6:
                closedate = (sd + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        sds = 3600 if atrasado else 0
        tds = 1800 if atrasado else 0
        cols = ("id, entities_id, name, content, status, priority, urgency, impact, "
                "itilcategories_id, locations_id, requesttypes_id, type, "
                "date, date_creation, date_mod, solvedate, closedate, "
                "solve_delay_stat, takeintoaccount_delay_stat, "
                "users_id_recipient, users_id_lastupdater, is_deleted")
        c.execute(
            f"INSERT INTO glpi_tickets ({cols}) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)",
            (tid, 1, name, content, status, prio, urg, imp, cat, loc,
             dcs, dcs, dms, solvedate, closedate, sds, tds, req, req),
        )
        c.execute("INSERT INTO glpi_tickets_users (tickets_id, users_id, type) VALUES (%s,%s,1)",
                  (tid, req))
        if tech:
            c.execute("INSERT INTO glpi_tickets_users (tickets_id, users_id, type) VALUES (%s,%s,2)",
                      (tid, tech))

    C = lambda k: next(iter([i for i in cat_ids if cats.get(i) == k]), next(iter(cat_ids)))
    L = lambda k: next(iter([i for i in loc_ids if locs.get(i) == k]), next(iter(loc_ids)))

    # 3a. Chamados nomeados que os testes referenciam (IDs explicitos)
    named = [
        (10361, "Computador extremamente lento ao iniciar",
         "Usuario relata que o computador demora mais de 10 minutos para iniciar. Ja foi feita limpeza de disco mas o problema persiste.",
         2, 3, 3, 3, C("Hardware"), L("Apoio"), 10, 5, True),
        (10362, "Usuario nao consegue fazer login no sistema",
         "Ao tentar logar aparece 'credenciais invalidas'. Ja tentou resetar senha mas nao recebeu o e-mail.",
         1, 4, 4, 3, C("Acesso e Login"), L("Cadastro"), None, 2, True),
        (10363, "Impressora nao conecta na rede",
         "Impressora do almoxarifado esta offline. LED de rede piscando. Tecnico ja verificou cabo e switch.",
         3, 2, 2, 2, C("Rede"), L("Almoxarifado"), 11, 7, False),
        (10367, "Certificado digital vencido - NF-e bloqueada",
         "Certificado digital A1 do setor venceu ontem. Notas fiscais eletronicas nao podem ser emitidas.",
         1, 4, 4, 4, C("Certificado Digital"), L("Auditoria"), None, 0, True),
        (10368, "Acesso remoto VPN nao estabelece conexao",
         "Usuario nao consegue conectar na VPN para trabalho remoto. Token retorna erro de autenticacao.",
         5, 3, 3, 2, C("Acesso Remoto"), L("Administracao"), 13, 10, False),
        (10369, "Ramal telefonico sem audio",
         "Ramal do setor de Atendimento esta mudo. Tecnico trocou o aparelho e o problema persiste.",
         6, 2, 2, 1, C("Telefonia"), L("Atendimento"), 12, 15, False),
        (10371, "Servico de e-mail fora do ar para todo setor",
         "Nenhum usuario do setor consegue acessar o Outlook. Erro: 'O Microsoft Outlook nao pode ser iniciado'.",
         2, 5, 5, 4, C("E-mail"), L("Apoio"), 14, 1, True),
    ]
    named_reqs = [15, 17, 8, 19, 18, 9, 8]
    for i, t in enumerate(named):
        tid, name, content, st, p, u, im, cat, loc, tech, days, atr = t
        req = named_reqs[i] if named_reqs[i] in usr_ids else reqs[0]
        insert_ticket(tid, name, content, st, p, u, im, cat, loc, req, tech, days, atr)
    log(f"  {len(named)} chamados nomeados inseridos")

    # 3b. Chamados genericos para volume/realismo
    topics = [
        ("Hardware", "Solicitacao de troca de mouse com defeito", "Mouse nao responde ao clique."),
        ("Software", "Erro ao abrir planilha no Excel", "Excel exibe mensagem de arquivo corrompido."),
        ("Rede", "Lentidao ao acessar sistema interno", "Paginas demoram a carregar no navegador."),
        ("Acesso e Login", "Solicitacao de novo usuario de rede", "Novo colaborador precisa de login."),
        ("E-mail", "Caixa de e-mail cheia", "Usuario nao recebe novos e-mails."),
        ("Acesso Remoto", "Configurar acesso remoto para home office", "Precisa de VPN configurada."),
        ("Telefonia", "Ramal com ruido na ligacao", "Chiado durante as chamadas."),
        ("Hardware", "Monitor sem imagem", "Tela permanece preta ao ligar."),
        ("Software", "Instalar leitor de PDF", "Necessario para abrir documentos."),
        ("Rede", "Ponto de rede sem conexao", "Tomada de rede nao da link."),
    ]
    generic_atrasados = 12   # + 4 nomeados atrasados = 16
    tid = 10372
    for n in range(33):
        top, name, content = topics[n % len(topics)]
        # distribui status; garante 12 atrasados
        if n < generic_atrasados:
            st = random.choice([1, 2, 4]); atr = True; days = random.randint(1, 40)
        else:
            st = random.choice([3, 5, 6, 5, 6]); atr = False; days = random.randint(5, 110)
        cat = C(top)
        loc = random.choice(list(loc_ids))
        req = random.choice(reqs)
        tech = random.choice(techs) if st != 1 else None
        insert_ticket(tid, name + f" ({tid})", content, st,
                      random.randint(2, 4), random.randint(2, 4), random.randint(1, 4),
                      cat, loc, req, tech, days, atr)
        tid += 1
    log(f"  {33} chamados genericos inseridos (total tickets ~40)")

    # ---------------------------------------------------------------
    # 4. Base de conhecimento ficticia (10 artigos)
    # ---------------------------------------------------------------
    author = 2
    kb = KB_ARTICLES
    for a in kb:
        c.execute(
            "INSERT INTO glpi_knowbaseitems (name, answer, users_id, view, is_faq, "
            "date_creation, date_mod) VALUES (%s,%s,%s,1,1,%s,%s)",
            (a["name"], a["answer"], author,
             NOW.strftime("%Y-%m-%d %H:%M:%S"), NOW.strftime("%Y-%m-%d %H:%M:%S")),
        )
        kid = c.lastrowid
        c.execute("INSERT INTO glpi_knowbaseitems_profiles "
                  "(knowbaseitems_id, profiles_id, entities_id, is_recursive, no_entity_restriction) "
                  "VALUES (%s,4,1,0,0)", (kid,))
    log(f"  {len(kb)} artigos de KB inseridos")

    cn.commit()

    # resumo
    def cnt(sql):
        c.execute(sql); return c.fetchone()[0]
    log("\n== RESUMO ==")
    log("  tickets entity1:", cnt("SELECT COUNT(*) FROM glpi_tickets WHERE entities_id=1 AND is_deleted=0"))
    log("  atrasados:", cnt(f"SELECT COUNT(*) FROM glpi_tickets WHERE entities_id=1 AND YEAR(date_creation)={cur_year} "
                            "AND is_deleted=0 AND status IN (1,2,4) AND (solve_delay_stat>0 OR takeintoaccount_delay_stat>0)"))
    log("  knowbaseitems:", cnt("SELECT COUNT(*) FROM glpi_knowbaseitems"))
    log("  usuarios com nome real (heuristica: realname nao começa com 'Anonimo'):",
        cnt("SELECT COUNT(*) FROM glpi_users WHERE id>=8 AND realname NOT LIKE 'Anonimo%' AND realname IS NOT NULL AND realname<>''"))
    c.close(); cn.close()


KB_ARTICLES = [
    {"name": "Computador lento - diagnostico e solucao",
     "answer": "<p><strong>Procedimento para diagnosticar computador lento:</strong></p><ol>"
     "<li>Verifique os programas que iniciam com o Windows (msconfig). Desabilite aplicativos desnecessarios.</li>"
     "<li>Execute o Gerenciador de Tarefas e verifique uso de CPU, memoria e disco.</li>"
     "<li>Limpe arquivos temporarios com a Limpeza de Disco.</li>"
     "<li>Verifique se o antivirus roda varredura em horario comercial.</li>"
     "<li>Execute <code>chkdsk /f</code> para verificar erros no disco.</li>"
     "<li>Se persistir, considere upgrade de RAM ou troca para SSD.</li></ol>"
     "<p><em>Ref: Procedimento TI-SUP-001</em></p>"},
    {"name": "Reset de senha e desbloqueio de usuario",
     "answer": "<p><strong>Procedimento para reset de senha:</strong></p><ol>"
     "<li>Acesse o Active Directory (ADUC) com credenciais administrativas.</li>"
     "<li>Localize o usuario na OU do setor.</li>"
     "<li>Botao direito &gt; Redefinir Senha.</li>"
     "<li>Informe senha temporaria conforme a politica.</li>"
     "<li>Marque 'O usuario deve alterar a senha no proximo logon'.</li>"
     "<li>Se necessario, desbloqueie a conta em Account &gt; Unlock Account.</li></ol>"
     "<p><strong>Causas comuns:</strong> multiplas tentativas incorretas, conta expirada.</p>"},
    {"name": "Impressora de rede - troubleshooting",
     "answer": "<p><strong>Solucionar problemas de impressora de rede:</strong></p><ol>"
     "<li>Verifique se a impressora esta ligada e conectada; LED de rede aceso.</li>"
     "<li>Execute <code>ping</code> para o IP da impressora.</li>"
     "<li>Acesse a interface web da impressora para checar suprimentos e rede.</li>"
     "<li>Remova e reinstale a impressora no computador do usuario.</li>"
     "<li>Verifique a fila no servidor de impressao.</li>"
     "<li>Reinicie o servico Spooler de Impressao.</li></ol>"
     "<p><strong>Causas comuns:</strong> cabo desconectado, IP conflitante, driver corrompido.</p>"},
    {"name": "E-mail Outlook - problemas comuns e solucoes",
     "answer": "<p><strong>Solucionar problemas de e-mail/Outlook:</strong></p><ol>"
     "<li>Verifique a conectividade de rede (acesso ao Exchange).</li>"
     "<li>Teste o Outlook Web Access (OWA) para isolar o problema.</li>"
     "<li>Crie um novo perfil do Outlook (Painel de Controle &gt; Mail).</li>"
     "<li>Limpe o cache de credenciais no Gerenciador de Credenciais.</li>"
     "<li>Execute o Assistente de Reparacao do Office.</li>"
     "<li>Como ultimo recurso, repare a instalacao do Office.</li></ol>"
     "<p><strong>Servidor:</strong> confirmar Exchange operacional e espaco em disco.</p>"},
    {"name": "Configuracao de VPN para acesso remoto",
     "answer": "<p><strong>Configurar e solucionar problemas de VPN:</strong></p><ol>"
     "<li>Verifique se o cliente VPN esta instalado e atualizado.</li>"
     "<li>Confirme credenciais: usuario de rede + senha + token.</li>"
     "<li>Verifique a URL/IP do servidor VPN.</li>"
     "<li>Teste conectividade com <code>ping</code> ao servidor.</li>"
     "<li>Verifique bloqueio de porta no firewall (UDP 443/500/4500).</li>"
     "<li>Sincronize o token se fora de sincronia; reinicie o cliente.</li></ol>"
     "<p><em>Se persistir, abrir chamado para a equipe de Redes.</em></p>"},
    {"name": "Renovacao de certificado digital A1/A3",
     "answer": "<p><strong>Renovacao de certificado digital:</strong></p><ol>"
     "<li>Identifique o tipo: A1 (arquivo) ou A3 (token/cartao).</li>"
     "<li>Acesse o site da Autoridade Certificadora com o token conectado.</li>"
     "<li>Localize 'Renovar Certificado' e siga o assistente.</li>"
     "<li>Valide a identidade por videoconferencia ou presencialmente.</li>"
     "<li>Baixe o novo certificado e instale no repositorio do Windows.</li>"
     "<li>Atualize a cadeia ICP-Brasil se necessario.</li>"
     "<li>Teste a emissao de uma NF-e de homologacao.</li></ol>"
     "<p><strong>Atencao:</strong> A1 vale 1 ano; renove com 30 dias de antecedencia.</p>"},
    {"name": "Backup e restauracao de arquivos",
     "answer": "<p><strong>Procedimento de backup e restauracao:</strong></p><ol>"
     "<li>Identifique os arquivos ou pastas a proteger.</li>"
     "<li>Verifique a rotina de backup agendada no servidor.</li>"
     "<li>Para restaurar, localize o ponto de restauracao mais recente.</li>"
     "<li>Copie os arquivos para um local temporario e valide a integridade.</li>"
     "<li>Documente a restauracao no chamado.</li></ol>"},
    {"name": "Lentidao na rede local - diagnostico",
     "answer": "<p><strong>Diagnostico de lentidao na rede:</strong></p><ol>"
     "<li>Teste a velocidade em mais de um equipamento.</li>"
     "<li>Verifique o uso de banda no switch/roteador.</li>"
     "<li>Cheque cabos e conexoes do ponto afetado.</li>"
     "<li>Reinicie os equipamentos de rede se necessario.</li>"
     "<li>Escale para a equipe de Redes se o problema for no backbone.</li></ol>"},
    {"name": "Instalacao de software homologado",
     "answer": "<p><strong>Instalacao de software padrao:</strong></p><ol>"
     "<li>Confirme que o software esta na lista de homologados.</li>"
     "<li>Baixe o instalador do repositorio interno.</li>"
     "<li>Execute a instalacao com privilegios administrativos.</li>"
     "<li>Registre a licenca e o numero do chamado.</li></ol>"},
    {"name": "Configuracao de impressora local USB",
     "answer": "<p><strong>Configurar impressora local USB:</strong></p><ol>"
     "<li>Conecte a impressora a porta USB do computador.</li>"
     "<li>Aguarde o reconhecimento automatico do Windows.</li>"
     "<li>Se necessario, instale o driver do fabricante.</li>"
     "<li>Imprima uma pagina de teste para validar.</li></ol>"},
]


if __name__ == "__main__":
    log("=" * 60)
    log("  Reconstrucao de ambiente sintetico - GLPI SQL AI")
    log("=" * 60)
    rebuild()
    log("\nConcluido. Reindexe a base vetorial e rode os testes.")
