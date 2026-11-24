/*
 * =====================================================================
 *  ATIVIDADE 01 - Sistema com sensor analógico (potenciômetro)
 * =====================================================================
 *  - LED verde pisca a cada 500 ms indicando que o sistema está ligado.
 *  - Potenciômetro (sensor analógico) lido continuamente.
 *  - LED amarelo varia o brilho conforme a posição do potenciômetro.
 *  - Buzzer apita (alerta) quando o valor passa do LIMITE.
 *  - Botão liga/desliga todo o sistema. Desligado: LEDs e buzzer apagados.
 *
 *  Sem delay(): cada parte é uma função que usa millis() e devolve o
 *  controle rápido, então todos os requisitos funcionam "ao mesmo tempo".
 *
 * ---------------------------------------------------------------------
 *  LIGAÇÕES (Arduino UNO)
 * ---------------------------------------------------------------------
 *  LED verde ....... D8  -> resistor 220 ohm -> GND
 *  LED amarelo ..... D9 (PWM) -> resistor 220 ohm -> GND
 *  Buzzer .......... D7 (+) / GND (-)
 *  Botão ........... D2 -> outro terminal no GND (usa INPUT_PULLUP)
 *  Potenciômetro ... pinos das pontas no 5V e GND, pino do meio no A0
 *  (se usar módulos com resistor na placa, ligue direto)
 * =====================================================================
 */

// ------------------------------ PINOS --------------------------------
const uint8_t PIN_LED_VERDE   = 8;
const uint8_t PIN_LED_AMARELO = 9;   // precisa ser PWM (~) para variar brilho
const uint8_t PIN_BUZZER      = 7;
const uint8_t PIN_BOTAO       = 2;
const uint8_t PIN_POT         = A0;

// --------------------------- CONFIGURAÇÕES ---------------------------
const unsigned long T_PISCA_VERDE = 500UL;  // pisca do LED verde
const unsigned long T_DEBOUNCE    = 50UL;   // anti-repique do botão
const unsigned long T_LEITURA     = 20UL;   // leitura do potenciômetro
const unsigned long T_BIPE        = 150UL;  // liga/desliga do bipe de alerta
const unsigned long T_SERIAL      = 500UL;  // envio de dados ao Monitor Serial

const int LIMITE_ALERTA = 800;       // 0 a 1023: acima disso o buzzer apita
const unsigned int FREQ_BUZZER = 2000;

// ------------------------- ESTADO DO SISTEMA -------------------------
bool sistemaLigado = true;

// LED verde
bool estadoVerde = false;
unsigned long ultimoPiscaVerde = 0;

// Botão (debounce)
bool leituraAnteriorBotao = HIGH;
bool estadoEstavelBotao   = HIGH;
unsigned long ultimaMudancaBotao = 0;

// Potenciômetro
int valorPot = 0;
unsigned long ultimaLeitura = 0;

// Buzzer
bool bipeLigado = false;
unsigned long ultimoBipe = 0;

unsigned long ultimoSerial = 0;

// =====================================================================
//  TAREFA: BOTÃO LIGA/DESLIGA (com debounce por millis)
// =====================================================================
void tarefaBotao() {
  bool leitura = digitalRead(PIN_BOTAO);

  // Qualquer mudança reinicia a contagem do debounce
  if (leitura != leituraAnteriorBotao) {
    ultimaMudancaBotao = millis();
    leituraAnteriorBotao = leitura;
  }

  // Leitura ficou estável pelo tempo de debounce
  if (millis() - ultimaMudancaBotao > T_DEBOUNCE && leitura != estadoEstavelBotao) {
    estadoEstavelBotao = leitura;

    if (estadoEstavelBotao == LOW) {  // botão foi apertado (INPUT_PULLUP)
      sistemaLigado = !sistemaLigado;
      Serial.println(sistemaLigado ? F(">>> SISTEMA LIGADO") : F(">>> SISTEMA DESLIGADO"));

      if (!sistemaLigado) desligarTudo();
    }
  }
}

// Apaga LEDs e buzzer
void desligarTudo() {
  digitalWrite(PIN_LED_VERDE, LOW);
  analogWrite(PIN_LED_AMARELO, 0);
  noTone(PIN_BUZZER);
  estadoVerde = false;
  bipeLigado  = false;
}

// =====================================================================
//  TAREFA: LED VERDE PISCANDO (sistema em funcionamento)
// =====================================================================
void tarefaLedVerde() {
  if (millis() - ultimoPiscaVerde >= T_PISCA_VERDE) {
    ultimoPiscaVerde = millis();
    estadoVerde = !estadoVerde;
    digitalWrite(PIN_LED_VERDE, estadoVerde);
  }
}

// =====================================================================
//  TAREFA: LEITURA DO POTENCIÔMETRO (sensor analógico)
// =====================================================================
void tarefaSensor() {
  if (millis() - ultimaLeitura >= T_LEITURA) {
    ultimaLeitura = millis();
    valorPot = analogRead(PIN_POT);  // 0 a 1023
  }
}

// =====================================================================
//  TAREFA: BRILHO DO LED AMARELO (proporcional ao potenciômetro)
// =====================================================================
void tarefaLedAmarelo() {
  int brilho = map(valorPot, 0, 1023, 0, 255);  // PWM vai de 0 a 255
  analogWrite(PIN_LED_AMARELO, brilho);
}

// =====================================================================
//  TAREFA: ALERTA SONORO (valor acima do limite)
// =====================================================================
void tarefaAlerta() {
  if (valorPot <= LIMITE_ALERTA) {
    if (bipeLigado) noTone(PIN_BUZZER);
    bipeLigado = false;
    return;
  }

  // Bipe intermitente enquanto estiver acima do limite
  if (millis() - ultimoBipe >= T_BIPE) {
    ultimoBipe = millis();
    bipeLigado = !bipeLigado;
    if (bipeLigado) tone(PIN_BUZZER, FREQ_BUZZER);
    else            noTone(PIN_BUZZER);
  }
}

// =====================================================================
//  TAREFA: MONITOR SERIAL (acompanhar os valores)
// =====================================================================
void tarefaSerial() {
  if (millis() - ultimoSerial >= T_SERIAL) {
    ultimoSerial = millis();
    Serial.print(F("Potenciometro: "));
    Serial.print(valorPot);
    Serial.print(F(" | Brilho: "));
    Serial.print(map(valorPot, 0, 1023, 0, 100));
    Serial.print(F("% | Alerta: "));
    Serial.println(valorPot > LIMITE_ALERTA ? F("SIM") : F("nao"));
  }
}

// =====================================================================
//  SETUP
// =====================================================================
void setup() {
  Serial.begin(9600);
  pinMode(PIN_LED_VERDE,   OUTPUT);
  pinMode(PIN_LED_AMARELO, OUTPUT);
  pinMode(PIN_BUZZER,      OUTPUT);
  pinMode(PIN_BOTAO,       INPUT_PULLUP);
  Serial.println(F(">>> SISTEMA LIGADO"));
}

// =====================================================================
//  LOOP - chama cada tarefa; nenhuma trava o processador
// =====================================================================
void loop() {
  tarefaBotao();            // sempre ativo: é ele que liga o sistema

  if (!sistemaLigado) return;  // desligado: nada mais executa

  tarefaLedVerde();
  tarefaSensor();
  tarefaLedAmarelo();
  tarefaAlerta();
  tarefaSerial();
}
