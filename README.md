# Underwater Optical-Acoustic Routing
Simulador + Implementacao do Algoritmo de Roteamento para Redes Aquáticas Ópticos-Acústicas <br/>
Desenvolvidos utilizando Python 3.4 

**Node**
===     
CBR <br/>
**UOARP** <br/> 
TDMA  <br/>
Acoustic Phy [1] | Optical Phy [2] <br/>

Esquema de transmissao de mensagens e consumo
===
- No cria mensagem e consome energia de transmissao
- Passa a mensagem para simulador
- Simulador verifica se mensagem pode ser entregue (alcance e erro)
- Se a mensagem for entregue, simulador coloca na caixa do no destino

Referências
===
    [1] Stojanovic, Milica. "On the relationship between capacity and distance in an underwater acoustic communication channel." ACM SIGMOBILE Mobile Computing and Communications Review 11.4 (2007): 34-43.
    [2] Anguita, Davide, et al. "Optical wireless underwater communication for AUV: Preliminary simulation and experimental results." OCEANS, 2011 IEEE-Spain. IEEE, 2011.
