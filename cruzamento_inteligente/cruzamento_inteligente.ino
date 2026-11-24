/*
 * =====================================================================
 *  CRUZAMENTO INTELIGENTE - Atividade 02
 * =====================================================================
 *  Dois semáforos (Via A e Via B), semáforo de pedestres com buzzer e
 *  modo de emergência (ambulância).
 *
 *  INOVAÇÃO: painel de monitoramento no Monitor Serial. O sistema mostra
 *  em tempo real a fase atual, o tempo restante, a cor de cada semáforo,
 *  se existe pedido de pedestre na fila e estatísticas de funcionamento
 *  (ciclos completos, travessias atendidas, emergências e tempo ligado).
 *
 *  Regras do projeto:
 *   - Sem delay(): todo controle de tempo é feito com millis().
 *   - O sistema é dividido em TAREFAS (funções) executadas em ciclo no
 *     loop(), como um escalonador cooperativo simples.
 *
 *  PRIORIDADES DAS TAREFAS (1 = mais alta):
 *   1. tarefaEmergencia() -> ambulância: força tudo vermelho
 *   2. tarefaPedestre()   -> travessia de pedestres (5 s + buzzer)
 *   3. tarefaSemaforos()  -> ciclo normal Via A / Via B
 *   4. tarefaBuzzer()     -> sinal sonoro da travessia
 *   5. tarefaSaidas()     -> escreve as cores nos LEDs RGB
 *   6. tarefaMonitor()    -> inovação: painel no Monitor Serial
 *  A prioridade é garantida pela ORDEM de execução no loop() e pelo
 *  fato de que tarefas de menor prioridade não alteram a fase quando
 *  uma de maior prioridade está ativa.
 *
 *  Os botões usam INTERRUPÇÃO (attachInterrupt): o pedido é gravado em
 *  uma flag no mesmo instante do aperto, então nunca é perdido, mesmo
 *  que o loop esteja ocupado com outra tarefa.
 *
 * ---------------------------------------------------------------------
 *  LIGAÇÕES (Arduino UNO)
 * ---------------------------------------------------------------------
 *  Botão pedestre ........ D2 (INT0) -> outro terminal no GND
 *  Botão ambulância ...... D3 (INT1) -> outro terminal no GND
 *     (usa INPUT_PULLUP: não precisa de resistor externo)
 *  Módulo RGB Via A ...... R=D4  G=D5  B=D6
 *  Módulo RGB Via B ...... R=D7  G=D8  B=D9
 *  Módulo RGB Pedestre ... R=D10 G=D11 B=D12
 *  Buzzer ................ A0 (+) / GND (-)
 *
 *  Cor amarela no módulo RGB = vermelho + verde acesos juntos.
 *  Monitor Serial: 9600 baud.
 * =====================================================================
 */

// ------------------------- CONFIGURAÇÃO ------------------------------
#define ANODO_COMUM 0  // 0 = módulo RGB catodo comum (HIGH acende)
                       // 1 = módulo RGB anodo comum  (LOW acende)

// ------------------------------ PINOS --------------------------------
const uint8_t PIN_BTN_PEDESTRE   = 2;   // interrupção INT0
const uint8_t PIN_BTN_AMBULANCIA = 3;   // interrupção INT1

const uint8_t A_R = 4,  A_G = 5,  A_B = 6;    // semáforo Via A
const uint8_t B_R = 7,  B_G = 8,  B_B = 9;    // semáforo Via B
const uint8_t P_R = 10, P_G = 11, P_B = 12;   // semáforo pedestre

const uint8_t PIN_BUZZER = A0;

// ------------------------------ TEMPOS (ms) --------------------------
const unsigned long T_VERDE         = 10000UL; // verde de cada via
const unsigned long T_AMARELO       = 2000UL;  // amarelo de cada via
// vermelho de cada via = verde + amarelo da outra = 12 s
const unsigned long T_TRAVESSIA     = 5000UL;  // verde do pedestre
const unsigned long T_FIM_TRAVESSIA = 1500UL;  // últimos 1,5 s: pisca e apita rápido
const unsigned long T_EMERGENCIA    = 10000UL; // duração do modo ambulância
const unsigned long T_LIMPEZA       = 2000UL;  // todos vermelhos (segurança)
const unsigned long T_DEBOUNCE      = 200UL;   // anti-repique dos botões
const unsigned long T_MONITOR       = 1000UL;  // atualização do painel serial

const unsigned int FREQ_BUZZER = 1000;  // Hz

// ------------------------------ TIPOS --------------------------------
enum Cor  { APAGADO, VERMELHO, AMARELO, VERDE, AZUL, MAGENTA };

enum Fase {
  A_VERDE,      // Via A verde,    Via B vermelho
  A_AMARELO,    // Via A amarelo,  Via B vermelho
  B_VERDE,      // Via B verde,    Via A vermelho
  B_AMARELO,    // Via B amarelo,  Via A vermelho
  TRAVESSIA,    // vias vermelhas, pedestre verde + buzzer
  LIMPEZA,      // tudo vermelho por alguns segundos (transição segura)
  EMERGENCIA    // ambulância: tudo vermelho
};

// ------------------------- ESTADO DO SISTEMA -------------------------
Fase fase                 = LIMPEZA;
Fase proximaAposLimpeza   = A_VERDE;  // para onde ir quando a LIMPEZA acabar
Fase proximaAposTravessia = A_VERDE;  // para onde ir quando a TRAVESSIA acabar
unsigned long inicioFase  = 0;        // millis() em que a fase atual começou

// Flags escritas nas interrupções -> precisam ser "volatile"
volatile bool pedidoPedestre   = false;
volatile bool pedidoAmbulancia = false;
volatile unsigned long ultimoIsrPedestre   = 0;
volatile unsigned long ultimoIsrAmbulancia = 0;

bool pedidoAnunciado = false;  // só para imprimir no Serial uma vez
bool buzzerLigado    = false;

// Cores atuais (usadas pelo painel do Monitor Serial)
Cor corAtualA = VERMELHO, corAtualB = VERMELHO, corAtualP = VERMELHO;

// Estatísticas (inovação)
unsigned int  totalCiclos      = 0;  // ciclos A+B completos
unsigned int  totalTravessias  = 0;
unsigned int  totalEmergencias = 0;
unsigned long ultimoMonitor    = 0;

// =====================================================================
//  ROTINAS DE INTERRUPÇÃO (ISR) - apenas REGISTRAM o pedido
// =====================================================================
void isrPedestre() {
  unsigned long agora = millis();
  if (agora - ultimoIsrPedestre > T_DEBOUNCE) {  // ignora repique
    pedidoPedestre = true;
    ultimoIsrPedestre = agora;
  }
}

void isrAmbulancia() {
  unsigned long agora = millis();
  if (agora - ultimoIsrAmbulancia > T_DEBOUNCE) {
    pedidoAmbulancia = true;
    ultimoIsrAmbulancia = agora;
  }
}

// =====================================================================
//  FUNÇÕES AUXILIARES
// =====================================================================
const char* nomeFase(Fase f) {
  switch (f) {
    case A_VERDE:    return "VIA A VERDE / VIA B VERMELHO";
    case A_AMARELO:  return "VIA A AMARELO / VIA B VERMELHO";
    case B_VERDE:    return "VIA B VERDE / VIA A VERMELHO";
    case B_AMARELO:  return "VIA B AMARELO / VIA A VERMELHO";
    case TRAVESSIA:  return "TRAVESSIA DE PEDESTRES";
    case LIMPEZA:    return "TODOS VERMELHOS (transicao)";
    case EMERGENCIA: return "EMERGENCIA - AMBULANCIA";
  }
  return "?";
}

const char* nomeCor(Cor c) {
  switch (c) {
    case APAGADO:  return "apagado";
    case VERMELHO: return "VERMELHO";
    case AMARELO:  return "AMARELO";
    case VERDE:    return "VERDE";
    case AZUL:     return "AZUL";
    case MAGENTA:  return "AGUARDE";
  }
  return "?";
}

// Duração total de cada fase (para o painel mostrar o tempo restante)
unsigned long duracaoFase(Fase f) {
  switch (f) {
    case A_VERDE:
    case B_VERDE:    return T_VERDE;
    case A_AMARELO:
    case B_AMARELO:  return T_AMARELO;
    case TRAVESSIA:  return T_TRAVESSIA;
    case LIMPEZA:    return T_LIMPEZA;
    case EMERGENCIA: return T_EMERGENCIA;
  }
  return 0;
}

unsigned long tempoNaFase() {
  return millis() - inicioFase;
}

// Imprime o instante atual no formato [mm:ss]
void imprimirRelogio() {
  unsigned long s = millis() / 1000;
  Serial.print(F("["));
  if (s / 60 < 10) Serial.print('0');
  Serial.print(s / 60);
  Serial.print(':');
  if (s % 60 < 10) Serial.print('0');
  Serial.print(s % 60);
  Serial.print(F("] "));
}

// Troca de fase: guarda o instante de início para contar o tempo com millis()
void mudarFase(Fase nova) {
  fase = nova;
  inicioFase = millis();
  imprimirRelogio();
  Serial.print(F(">>> "));
  Serial.println(nomeFase(nova));
}

// Lê e limpa uma flag da ISR de forma atômica
bool consumirFlag(volatile bool &flag) {
  noInterrupts();
  bool valor = flag;
  flag = false;
  interrupts();
  return valor;
}

// Escreve uma cor em um módulo RGB
void escreverCor(uint8_t pr, uint8_t pg, uint8_t pb, Cor cor) {
  bool r = (cor == VERMELHO || cor == AMARELO || cor == MAGENTA);
  bool g = (cor == VERDE    || cor == AMARELO);
  bool b = (cor == AZUL     || cor == MAGENTA);
#if ANODO_COMUM
  r = !r; g = !g; b = !b;
#endif
  digitalWrite(pr, r);
  digitalWrite(pg, g);
  digitalWrite(pb, b);
}

void ligarBuzzer(bool ligar) {
  if (ligar && !buzzerLigado)       tone(PIN_BUZZER, FREQ_BUZZER);
  else if (!ligar && buzzerLigado)  noTone(PIN_BUZZER);
  buzzerLigado = ligar;
}

// Chamado quando um amarelo termina: é o ponto SEGURO para atender
// o pedestre (a outra via já está vermelha e esta acabou de fechar).
void aposAmarelo(Fase proximaNormal) {
  if (pedidoPedestre) {
    proximaAposTravessia = proximaNormal;  // depois da travessia, segue o ciclo
    mudarFase(TRAVESSIA);
  } else {
    mudarFase(proximaNormal);
  }
}

// =====================================================================
//  TAREFA 1 (PRIORIDADE MÁXIMA) - EMERGÊNCIA / AMBULÂNCIA
// =====================================================================
void tarefaEmergencia() {
  // Botão da ambulância: interrompe QUALQUER fase imediatamente.
  // Apertar de novo durante a emergência reinicia o tempo (estende).
  if (consumirFlag(pedidoAmbulancia)) {
    if (fase != EMERGENCIA) totalEmergencias++;
    mudarFase(EMERGENCIA);
    return;
  }

  // Fim da emergência: passa por LIMPEZA (todos vermelhos) e reinicia o ciclo
  if (fase == EMERGENCIA && tempoNaFase() >= T_EMERGENCIA) {
    proximaAposLimpeza = A_VERDE;
    mudarFase(LIMPEZA);
  }
}

// =====================================================================
//  TAREFA 2 - TRAVESSIA DE PEDESTRES
// =====================================================================
void tarefaPedestre() {
  if (fase == EMERGENCIA) return;  // emergência tem prioridade

  // Informa (uma vez) que o pedido foi registrado e está na fila
  if (pedidoPedestre && !pedidoAnunciado && fase != TRAVESSIA) {
    imprimirRelogio();
    Serial.println(F("    Pedido de pedestre REGISTRADO (aguardando fim do amarelo)"));
    pedidoAnunciado = true;
  }

  if (fase != TRAVESSIA) return;

  // Durante a travessia o pedido já está sendo atendido:
  // novos apertos são descartados.
  pedidoPedestre  = false;
  pedidoAnunciado = false;

  if (tempoNaFase() >= T_TRAVESSIA) {
    totalTravessias++;
    mudarFase(proximaAposTravessia);
  }
}

// =====================================================================
//  TAREFA 3 - CICLO NORMAL DOS SEMÁFOROS (Via A x Via B)
// =====================================================================
void tarefaSemaforos() {
  if (fase == EMERGENCIA || fase == TRAVESSIA) return;  // maior prioridade ativa

  unsigned long t = tempoNaFase();

  switch (fase) {
    case A_VERDE:
      if (t >= T_VERDE) mudarFase(A_AMARELO);
      break;

    case A_AMARELO:
      if (t >= T_AMARELO) aposAmarelo(B_VERDE);
      break;

    case B_VERDE:
      if (t >= T_VERDE) mudarFase(B_AMARELO);
      break;

    case B_AMARELO:
      if (t >= T_AMARELO) {
        totalCiclos++;  // Via A e Via B já abriram: um ciclo completo
        aposAmarelo(A_VERDE);
      }
      break;

    case LIMPEZA:
      if (t >= T_LIMPEZA) mudarFase(proximaAposLimpeza);
      break;

    default:
      break;
  }
}

// =====================================================================
//  TAREFA 4 - BUZZER (sinal sonoro durante a travessia)
//  Bipe lento durante a travessia e bipe rápido no final, avisando que
//  o tempo está acabando (acessibilidade para deficientes visuais).
// =====================================================================
void tarefaBuzzer() {
  if (fase != TRAVESSIA) {
    ligarBuzzer(false);
    return;
  }

  unsigned long t = tempoNaFase();
  unsigned long restante = (t < T_TRAVESSIA) ? T_TRAVESSIA - t : 0;
  unsigned long periodo  = (restante > T_FIM_TRAVESSIA) ? 500UL : 200UL;

  ligarBuzzer((t % periodo) < (periodo / 2));
}

// =====================================================================
//  TAREFA 5 - SAÍDAS: define a cor de cada módulo RGB conforme a fase
//  (única função que escreve nos LEDs -> evita conflito entre tarefas)
// =====================================================================
void tarefaSaidas() {
  Cor corA = VERMELHO, corB = VERMELHO, corP = VERMELHO;
  unsigned long t = tempoNaFase();

  switch (fase) {
    case A_VERDE:   corA = VERDE;   break;
    case A_AMARELO: corA = AMARELO; break;
    case B_VERDE:   corB = VERDE;   break;
    case B_AMARELO: corB = AMARELO; break;

    case TRAVESSIA: {
      unsigned long restante = (t < T_TRAVESSIA) ? T_TRAVESSIA - t : 0;
      bool piscaRapido = ((t / 250) % 2) == 0;
      // verde fixo; nos últimos 1,5 s o verde do pedestre pisca
      corP = (restante > T_FIM_TRAVESSIA || piscaRapido) ? VERDE : APAGADO;
      break;
    }

    case LIMPEZA:
    case EMERGENCIA:
    default:
      break;  // tudo vermelho
  }

  // Pedido de pedestre registrado -> semáforo do pedestre fica MAGENTA
  // (vermelho + azul) = "aguarde, seu pedido foi aceito".
  if (pedidoPedestre && fase != TRAVESSIA) corP = MAGENTA;

  escreverCor(A_R, A_G, A_B, corA);
  escreverCor(B_R, B_G, B_B, corB);
  escreverCor(P_R, P_G, P_B, corP);

  corAtualA = corA;
  corAtualB = corB;
  corAtualP = corP;
}

// =====================================================================
//  TAREFA 6 - INOVAÇÃO: PAINEL DE MONITORAMENTO NO MONITOR SERIAL
//  A cada 1 segundo mostra o estado completo do cruzamento. Serve para
//  acompanhar o funcionamento, depurar e demonstrar o sistema.
//  Prioridade mais baixa: só imprime, nunca altera o estado.
// =====================================================================
void tarefaMonitor() {
  if (millis() - ultimoMonitor < T_MONITOR) return;
  ultimoMonitor = millis();

  unsigned long t   = tempoNaFase();
  unsigned long dur = duracaoFase(fase);
  unsigned long restante = (t < dur) ? (dur - t + 999) / 1000 : 0;  // em s, arredondado p/ cima

  imprimirRelogio();
  Serial.print(F("Restam "));
  if (restante < 10) Serial.print(' ');
  Serial.print(restante);
  Serial.print(F("s | Via A: "));   Serial.print(nomeCor(corAtualA));
  Serial.print(F(" | Via B: "));    Serial.print(nomeCor(corAtualB));
  Serial.print(F(" | Pedestre: ")); Serial.print(nomeCor(corAtualP));
  Serial.print(F(" | Pedido: "));   Serial.print(pedidoPedestre ? F("SIM") : F("nao"));
  Serial.print(F(" | Ciclos: "));   Serial.print(totalCiclos);
  Serial.print(F(" Travessias: ")); Serial.print(totalTravessias);
  Serial.print(F(" Emergencias: "));Serial.println(totalEmergencias);
}

// =====================================================================
//  SETUP
// =====================================================================
void setup() {
  Serial.begin(9600);

  const uint8_t saidas[] = { A_R, A_G, A_B, B_R, B_G, B_B, P_R, P_G, P_B, PIN_BUZZER };
  for (uint8_t i = 0; i < sizeof(saidas); i++) pinMode(saidas[i], OUTPUT);

  pinMode(PIN_BTN_PEDESTRE,   INPUT_PULLUP);
  pinMode(PIN_BTN_AMBULANCIA, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_BTN_PEDESTRE),   isrPedestre,   FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_BTN_AMBULANCIA), isrAmbulancia, FALLING);

  Serial.println(F("=================================================="));
  Serial.println(F("        CRUZAMENTO INTELIGENTE - INICIADO"));
  Serial.println(F("  Botao D2 = pedestre | Botao D3 = ambulancia"));
  Serial.println(F("  Painel atualizado a cada 1 segundo"));
  Serial.println(F("=================================================="));

  // Começa com todos vermelhos por segurança e depois libera a Via A
  proximaAposLimpeza = A_VERDE;
  mudarFase(LIMPEZA);
}

// =====================================================================
//  LOOP - ESCALONADOR COOPERATIVO
//  Cada tarefa executa rápido (sem delay) e devolve o controle.
//  A ordem abaixo define a PRIORIDADE.
// =====================================================================
void loop() {
  tarefaEmergencia();   // 1 - maior prioridade
  tarefaPedestre();     // 2
  tarefaSemaforos();    // 3
  tarefaBuzzer();       // 4
  tarefaSaidas();       // 5 - atualiza os LEDs com o estado final
  tarefaMonitor();      // 6 - inovação: painel no Monitor Serial
}
