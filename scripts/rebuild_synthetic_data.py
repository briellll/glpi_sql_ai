"""
Reconstrucao do ambiente de teste sintetico do GLPI SQL AI.

Remove TODOS os dados reais (chamados, base de conhecimento, seguidores, solucoes)
e repopula o banco com dados ficticios realistas, modelados nos campos usados em
chamados reais. Tambem anonimiza usuarios e nomes de referencia (setores, categorias,
grupos) para que nenhum dado pessoal/organizacional real permaneca no banco.

Uso:
    poetry run python scripts/rebuild_synthetic_data.py

Depois, rode scripts/anonimizar_banco.py (remove e-mails, telefones, logins,
credenciais e historicos reais que este script nao cobre), reindexe a base
vetorial e rode os testes.
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
    # 4. Base de conhecimento ficticia (30 artigos)
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
    {"name": "Impressora com papel atolado",
     "answer": "<p><strong>Procedimento para remover papel atolado:</strong></p><ol>"
     "<li>Desligue a impressora e desconecte o cabo de energia.</li>"
     "<li>Abra a tampa de acesso seguindo as setas indicadas no equipamento.</li>"
     "<li>Retire o papel preso puxando sempre no sentido da saida, sem rasgar.</li>"
     "<li>Remova os restos de papel e verifique os roletes de tracao.</li>"
     "<li>Confira a bandeja e nao ultrapasse a marca de capacidade maxima.</li>"
     "<li>Ligue a impressora e imprima uma pagina de teste.</li></ol>"
     "<p><strong>Causas comuns:</strong> papel umido, folhas dobradas, bandeja sobrecarregada.</p>"},
    {"name": "Driver de impressora - instalacao e atualizacao",
     "answer": "<p><strong>Instalar ou atualizar driver de impressora:</strong></p><ol>"
     "<li>Identifique o modelo exato da impressora e o sistema operacional.</li>"
     "<li>Baixe o driver mais recente no site do fabricante ou no repositorio interno.</li>"
     "<li>Remova o driver antigo em Painel de Controle &gt; Dispositivos e Impressoras.</li>"
     "<li>Nas propriedades da impressora, aba Avancado, exclua o driver corrompido.</li>"
     "<li>Execute o instalador baixado e siga o assistente.</li>"
     "<li>Adicione a impressora novamente e imprima uma pagina de teste.</li></ol>"
     "<p><strong>Atencao:</strong> a instalacao exige perfil de administrador local.</p>"},
    {"name": "Wi-Fi corporativo nao conecta",
     "answer": "<p><strong>Reconectar o Wi-Fi corporativo:</strong></p><ol>"
     "<li>Confirme que o Wi-Fi esta ligado e o modo aviao esta desativado.</li>"
     "<li>Selecione a rede corporativa e informe as credenciais do dominio.</li>"
     "<li>Se aparecer aviso de certificado, valide o servidor de autenticacao com a TI.</li>"
     "<li>Em Configuracoes &gt; Rede e Internet &gt; Wi-Fi, use Esquecer a rede.</li>"
     "<li>Conecte novamente e digite usuario e senha atualizados.</li>"
     "<li>Se persistir, remova o perfil salvo e faca logon na rede cabeada.</li></ol>"},
    {"name": "Ponto de rede sem link",
     "answer": "<p><strong>Verificar ponto de rede sem link:</strong></p><ol>"
     "<li>Confirme se o LED da placa de rede esta apagado no computador.</li>"
     "<li>Substitua o patch cord e confira o encaixe nos dois extremos.</li>"
     "<li>Teste outro cabo entre a tomada de rede e a maquina.</li>"
     "<li>Teste a mesma tomada com um notebook que funcione na rede.</li>"
     "<li>Verifique no switch se a porta esta ativa e com LED aceso.</li>"
     "<li>Se a porta estiver desabilitada, acione a equipe de Redes.</li></ol>"
     "<p><strong>Causas comuns:</strong> cabo rompido, conector solto, porta do switch desativada.</p>"},
    {"name": "Sites e sistemas nao abrem por nome (DNS)",
     "answer": "<p><strong>Resolver falha de resolucao de nomes:</strong></p><ol>"
     "<li>Teste o acesso ao sistema pelo endereco IP para confirmar o problema.</li>"
     "<li>Abra o Prompt de Comando como administrador.</li>"
     "<li>Execute <code>ipconfig /flushdns</code> para limpar o cache local.</li>"
     "<li>Confira o servidor DNS configurado com <code>ipconfig /all</code>.</li>"
     "<li>Teste a resolucao com <code>nslookup nome_do_sistema</code>.</li>"
     "<li>Reinicie o servico Cliente DNS e tente o acesso novamente.</li></ol>"
     "<p><strong>Observacao:</strong> se o nslookup falhar, acione a equipe de Redes.</p>"},
    {"name": "Senha expirada - troca obrigatoria no logon",
     "answer": "<p><strong>Trocar senha expirada no logon:</strong></p><ol>"
     "<li>Na tela de logon, informe usuario e senha atual.</li>"
     "<li>Aguarde o aviso de que a senha expirou pela politica do dominio.</li>"
     "<li>Digite a nova senha conforme os requisitos de complexidade.</li>"
     "<li>Confirme a nova senha no campo de repeticao.</li>"
     "<li>Se a tela nao aparecer, pressione Ctrl+Alt+Del e escolha Alterar senha.</li>"
     "<li>Faca logon novamente e valide o acesso aos sistemas.</li></ol>"},
    {"name": "Caixa de correio cheia - limite de armazenamento",
     "answer": "<p><strong>Liberar espaco na caixa de correio:</strong></p><ol>"
     "<li>Verifique o aviso de cota no Outlook ou no webmail.</li>"
     "<li>Ordene os itens por tamanho e exclua os anexos maiores.</li>"
     "<li>Arquive mensagens antigas em arquivo local ou no OneDrive.</li>"
     "<li>Esvazie as pastas Itens Excluidos e Lixo Eletronico.</li>"
     "<li>Sincronize a caixa e confirme a liberacao do espaco.</li></ol>"
     "<p><strong>Atencao:</strong> o limite da caixa e definido pela politica de TI.</p>"},
    {"name": "Configuracao de e-mail corporativo no celular",
     "answer": "<p><strong>Configurar e-mail corporativo no celular:</strong></p><ol>"
     "<li>Instale o aplicativo de e-mail homologado pela empresa.</li>"
     "<li>Escolha a opcao de conta corporativa ou Exchange.</li>"
     "<li>Informe o endereco de e-mail completo e a senha de rede.</li>"
     "<li>Aceite as politicas de seguranca solicitadas pelo servidor.</li>"
     "<li>Aguarde a sincronizacao de e-mails, calendario e contatos.</li>"
     "<li>Se solicitado, cadastre o codigo de verificacao em dois fatores.</li></ol>"},
    {"name": "Computador nao liga",
     "answer": "<p><strong>Verificar computador que nao liga:</strong></p><ol>"
     "<li>Confirme se a tomada tem energia e teste outro equipamento nela.</li>"
     "<li>Verifique o cabo de forca e a chave da fonte na parte traseira.</li>"
     "<li>Com o cabo de forca desconectado, pressione o botao de power por 10 segundos para descarregar a placa.</li>"
     "<li>Observe se ha LED aceso ou ruido de cooler ao ligar.</li>"
     "<li>Se for notebook, remova a bateria e teste apenas com a fonte.</li>"
     "<li>Se nao houver sinal, encaminhe o equipamento para manutencao.</li></ol>"},
    {"name": "Tela azul (BSOD) - diagnostico",
     "answer": "<p><strong>Diagnosticar tela azul (BSOD):</strong></p><ol>"
     "<li>Anote o codigo de parada exibido na tela azul.</li>"
     "<li>Reinicie o computador e verifique se o sistema inicia normalmente.</li>"
     "<li>Liste os drivers e programas instalados nas ultimas 48 horas.</li>"
     "<li>Desinstale ou atualize o driver suspeito.</li>"
     "<li>Execute o teste de memoria do Windows com <code>mdsched</code>.</li>"
     "<li>Verifique a saude do disco com <code>chkdsk /f</code>.</li></ol>"
     "<p><strong>Causas comuns:</strong> driver incompativel, memoria com defeito, disco com setores ruins.</p>"},
    {"name": "Mapeamento de unidade de rede",
     "answer": "<p><strong>Mapear unidade de rede:</strong></p><ol>"
     "<li>Confirme o caminho da pasta compartilhada com a equipe de TI.</li>"
     "<li>Abra o Explorador de Arquivos e acesse Este Computador.</li>"
     "<li>Clique em Mapear unidade de rede.</li>"
     "<li>Escolha uma letra livre e informe o caminho da pasta.</li>"
     "<li>Marque Reconectar ao entrar e clique em Concluir.</li>"
     "<li>Informe as credenciais de dominio se forem solicitadas.</li></ol>"},
    {"name": "Permissao de acesso a pasta compartilhada",
     "answer": "<p><strong>Solicitar acesso a pasta compartilhada:</strong></p><ol>"
     "<li>Identifique o caminho da pasta e o nivel de acesso necessario.</li>"
     "<li>Abra um chamado informando usuario, setor e justificativa.</li>"
     "<li>A TI valida a aprovacao do gestor responsavel pela pasta.</li>"
     "<li>O acesso e concedido por grupo do Active Directory.</li>"
     "<li>O usuario deve sair e entrar novamente para atualizar o token.</li>"
     "<li>Teste a abertura e a gravacao de um arquivo na pasta.</li></ol>"},
    {"name": "Remocao de virus e malware",
     "answer": "<p><strong>Remover virus e malware:</strong></p><ol>"
     "<li>Desconecte a maquina da rede para evitar propagacao.</li>"
     "<li>Execute a varredura completa com o antivirus corporativo.</li>"
     "<li>Coloque os itens detectados em quarentena e revise a lista.</li>"
     "<li>Execute tambem a ferramenta de remocao de software malicioso.</li>"
     "<li>Atualize as assinaturas do antivirus e repita a varredura.</li>"
     "<li>Troque as senhas do usuario apos a limpeza.</li>"
     "<li>Reconecte a rede apenas com a maquina validada.</li></ol>"},
    {"name": "Atualizacao do Windows travada",
     "answer": "<p><strong>Destravar a atualizacao do Windows:</strong></p><ol>"
     "<li>Abra o Prompt de Comando como administrador.</li>"
     "<li>Pare o servico Windows Update com <code>net stop wuauserv</code>.</li>"
     "<li>Renomeie a pasta C:\\Windows\\SoftwareDistribution para .old.</li>"
     "<li>Reinicie o servico com <code>net start wuauserv</code>.</li>"
     "<li>Execute <code>sfc /scannow</code> para corrigir arquivos do sistema.</li>"
     "<li>Abra o Windows Update e clique em Verificar atualizacoes.</li></ol>"},
    {"name": "Monitor sem imagem",
     "answer": "<p><strong>Resolver monitor sem imagem:</strong></p><ol>"
     "<li>Verifique se o monitor esta ligado e com LED de energia aceso.</li>"
     "<li>Reaperte o cabo de video nas duas pontas.</li>"
     "<li>Confirme a entrada correta no menu do monitor (HDMI, DisplayPort ou VGA).</li>"
     "<li>Teste outro cabo de video.</li>"
     "<li>Teste o monitor em outro computador e vice-versa.</li>"
     "<li>Se houver imagem na BIOS, verifique o driver de video.</li></ol>"},
    {"name": "Teclado ou mouse sem resposta",
     "answer": "<p><strong>Reativar teclado ou mouse sem resposta:</strong></p><ol>"
     "<li>Verifique se o cabo USB esta firme ou se o receptor sem fio esta conectado.</li>"
     "<li>Troque o periferico para outra porta USB, preferindo a traseira.</li>"
     "<li>No caso de sem fio, substitua ou recarregue as pilhas.</li>"
     "<li>Reemparelhe o dispositivo com o receptor.</li>"
     "<li>Teste o periferico em outro computador.</li>"
     "<li>No Gerenciador de Dispositivos, verifique erros e reinstale o driver.</li></ol>"},
    {"name": "Arquivo do Excel corrompido - recuperacao",
     "answer": "<p><strong>Recuperar arquivo do Excel corrompido:</strong></p><ol>"
     "<li>No Excel, acesse Arquivo &gt; Abrir &gt; Procurar e selecione o arquivo.</li>"
     "<li>Na seta ao lado do botao Abrir, escolha Abrir e Reparar; se o reparo falhar, use Extrair Dados.</li>"
     "<li>Verifique as Versoes Anteriores do arquivo nas propriedades.</li>"
     "<li>Procure copias na lixeira, no OneDrive ou no backup do servidor.</li>"
     "<li>Verifique a pasta de AutoRecuperacao do Office em busca de versoes recentes.</li>"
     "<li>Restaure a copia valida e salve com um novo nome.</li></ol>"},
    {"name": "Recuperacao de documento do Office nao salvo",
     "answer": "<p><strong>Recuperar documento do Office nao salvo:</strong></p><ol>"
     "<li>Abra o aplicativo e acesse Arquivo &gt; Abrir &gt; Recuperar Documentos.</li>"
     "<li>Escolha a opcao de documentos nao salvos.</li>"
     "<li>Verifique a pasta AutoRecuperacao do Office em Arquivos Temporarios.</li>"
     "<li>Localize o arquivo mais recente pelo nome e data.</li>"
     "<li>Abra o arquivo e salve imediatamente em local seguro.</li>"
     "<li>Se nao encontrar, acione a TI para tentar a recuperacao no perfil.</li></ol>"},
    {"name": "Assinatura de e-mail padrao no Outlook",
     "answer": "<p><strong>Criar a assinatura padrao no Outlook:</strong></p><ol>"
     "<li>Abra o Outlook e acesse Arquivo &gt; Opcoes &gt; Email.</li>"
     "<li>Clique em Assinaturas e selecione Novo.</li>"
     "<li>Informe nome, cargo, setor e contatos conforme o modelo institucional.</li>"
     "<li>Defina a fonte e as cores aprovadas pela comunicacao.</li>"
     "<li>Marque a assinatura como padrao para novas mensagens e respostas.</li>"
     "<li>Envie um e-mail de teste para validar a formatacao.</li></ol>"},
    {"name": "Erro de certificado SSL no navegador",
     "answer": "<p><strong>Resolver erro de certificado SSL no navegador:</strong></p><ol>"
     "<li>Verifique se a data e a hora do computador estao corretas.</li>"
     "<li>Confirme o endereco do sistema interno e se o cadeado aparece.</li>"
     "<li>Abra os detalhes do certificado e verifique a validade e a cadeia.</li>"
     "<li>Instale o certificado raiz interno no repositorio do Windows.</li>"
     "<li>Limpe o cache do navegador e teste em uma janela anonima.</li>"
     "<li>Se o erro persistir, encaminhe o caso para a TI com a mensagem exibida.</li></ol>"},
]


def reindex_vector_store():
    """Reindexa o ChromaDB com os artigos atualmente no banco.

    Sem esta etapa o banco relacional e o indice vetorial ficam dessincronizados:
    o RAG continuaria respondendo com os artigos antigos.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        log("  [AVISO] OPENAI_API_KEY nao configurada. Pulando reindexacao vetorial.")
        return

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from glpi_sql_ai.vector_store import KBVectorStore

    cn = mysql.connector.connect(**DB)
    c = cn.cursor()
    c.execute("SELECT id, name, answer FROM glpi_knowbaseitems ORDER BY id")
    articles = [
        {"id": r[0], "name": r[1] or "", "answer": r[2] or ""} for r in c.fetchall()
    ]
    c.close()
    cn.close()

    if not articles:
        log("  [AVISO] Nenhum artigo encontrado para indexar.")
        return

    persist_dir = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    vs = KBVectorStore(api_key=api_key, persist_dir=persist_dir)
    count = vs.index_articles(articles)
    log(f"  Base vetorial reindexada: {count} artigos no ChromaDB.")


if __name__ == "__main__":
    log("=" * 60)
    log("  Reconstrucao de ambiente sintetico - GLPI SQL AI")
    log("=" * 60)
    rebuild()
    log("\nReindexando base vetorial...")
    reindex_vector_store()
    log("\nConcluido. Ambiente sintetico pronto (banco + indice vetorial).")
