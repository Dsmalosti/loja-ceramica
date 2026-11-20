// Malosti Arte Cerâmica · menu do celular, topo da home, carrossel e revelar ao rolar.
// Melhoria progressiva: sem este arquivo o site continua legível e navegável.
// Cada parte só roda se o elemento dela existir na página.
(function () {
  'use strict';
  var raiz = document.documentElement;
  raiz.classList.add('js');
  var reduzir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function iniciar() {
    var topo = document.getElementById('topo');
    var banner = document.getElementById('inicio');

    /* ---------- Menu do celular ---------- */
    if (topo) {
      var botaoMenu = topo.querySelector('.topo__botao');
      topo.classList.add('topo--js');
      if (botaoMenu) {
        botaoMenu.hidden = false;
        var menu = function (abrir) {
          topo.classList.toggle('topo--aberto', abrir);
          botaoMenu.setAttribute('aria-expanded', String(abrir));
          botaoMenu.querySelector('.sr-only').textContent = abrir ? 'Fechar menu' : 'Abrir menu';
        };
        botaoMenu.addEventListener('click', function () {
          menu(botaoMenu.getAttribute('aria-expanded') !== 'true');
        });
        topo.querySelectorAll('.menu a').forEach(function (a) {
          a.addEventListener('click', function () { menu(false); });
        });
        document.addEventListener('keydown', function (e) { if (e.key === 'Escape') menu(false); });
      }
    }

    /* ---------- Home: topo fica sólido depois do banner ---------- */
    if (topo && banner) {
      var atualizarTopo = function () {
        var passou = window.scrollY > banner.offsetHeight - topo.offsetHeight - 10;
        topo.classList.toggle('topo--solido', passou);
        // WhatsApp flutuante só aparece depois do banner
        raiz.classList.toggle('no-banner', !passou);
      };
      atualizarTopo();
      window.addEventListener('scroll', atualizarTopo, { passive: true });
      window.addEventListener('resize', atualizarTopo);
    }

    /* ---------- Home: carrossel do banner ---------- */
    if (banner) carrossel(banner);

    /* ---------- Loja: filtro fecha ao clicar fora ou com Esc ---------- */
    var filtroLoja = document.querySelector('.filtro-loja');
    if (filtroLoja) {
      document.addEventListener('click', function (e) {
        if (filtroLoja.open && !filtroLoja.contains(e.target)) filtroLoja.open = false;
      });
      filtroLoja.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && filtroLoja.open) {
          filtroLoja.open = false;
          filtroLoja.querySelector('summary').focus();
        }
      });
    }

    /* ---------- Campos de senha: botão Mostrar / Ocultar ---------- */
    document.querySelectorAll('input[type="password"]').forEach(mostrarSenha);

    /* ---------- Endereço: o CEP preenche rua, bairro, cidade e estado ---------- */
    var cep = document.getElementById('cep');
    if (cep && document.getElementById('logradouro')) buscaCep(cep);

    /* ---------- Revelar ao rolar ---------- */
    var alvos = document.querySelectorAll('.revelar');
    if (!('IntersectionObserver' in window) || reduzir) {
      alvos.forEach(function (el) { el.classList.add('visivel'); });
    } else {
      var obs = new IntersectionObserver(function (entradas) {
        entradas.forEach(function (en) {
          if (en.isIntersecting) { en.target.classList.add('visivel'); obs.unobserve(en.target); }
        });
      }, { rootMargin: '0px 0px -10% 0px' });
      alvos.forEach(function (el) { obs.observe(el); });
    }
  }

  // O botão só existe com JS; sem ele o campo continua um campo de senha comum.
  function mostrarSenha(campo) {
    var caixa = document.createElement('span');
    caixa.className = 'campo-senha';
    campo.parentNode.insertBefore(caixa, campo);
    caixa.appendChild(campo);

    var botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'campo-senha__botao';
    botao.textContent = 'Mostrar';
    botao.setAttribute('aria-pressed', 'false');
    botao.setAttribute('aria-controls', campo.id);
    botao.setAttribute('aria-label', 'Mostrar senha');
    caixa.appendChild(botao);

    function definir(visivel) {
      campo.type = visivel ? 'text' : 'password';
      botao.textContent = visivel ? 'Ocultar' : 'Mostrar';
      botao.setAttribute('aria-pressed', String(visivel));
      botao.setAttribute('aria-label', visivel ? 'Ocultar senha' : 'Mostrar senha');
    }
    botao.addEventListener('click', function () {
      definir(campo.type === 'password');
      campo.focus();
    });
    // Ao enviar volta a ser senha: o gerenciador de senhas do navegador reconhece e oferece salvar
    if (campo.form) campo.form.addEventListener('submit', function () { definir(false); });
  }

  // ViaCEP (serviço público e gratuito, sem chave). Só o CEP sai do navegador da pessoa;
  // nada passa pelo nosso servidor. Se o serviço falhar, a pessoa preenche à mão como antes.
  function buscaCep(cep) {
    var campos = {
      logradouro: document.getElementById('logradouro'),
      bairro: document.getElementById('bairro'),
      cidade: document.getElementById('cidade'),
      uf: document.getElementById('uf')
    };
    var numero = document.getElementById('numero');
    var aviso = document.createElement('p');
    aviso.className = 'cep-aviso';
    aviso.id = 'cep-aviso';
    aviso.setAttribute('aria-live', 'polite');
    cep.setAttribute('aria-describedby', 'cep-aviso');
    // Fica embaixo da linha do CEP (e não dentro da coluna estreita dele), com a largura do formulário
    var bloco = cep.closest('.campos') || cep;
    bloco.parentNode.insertBefore(aviso, bloco.nextSibling);
    var ultimo = cep.value.replace(/\D/g, '');

    function avisar(texto, erro) {
      aviso.textContent = texto;
      aviso.classList.toggle('cep-aviso--erro', !!erro);
    }

    cep.addEventListener('input', function () {
      var digitos = cep.value.replace(/\D/g, '').slice(0, 8);
      cep.value = digitos.length > 5 ? digitos.slice(0, 5) + '-' + digitos.slice(5) : digitos;
      if (digitos.length < 8) { avisar(''); return; }
      if (digitos === ultimo) return;
      ultimo = digitos;
      buscar(digitos);
    });

    function buscar(digitos) {
      avisar('Buscando o endereço…');
      var controle = 'AbortController' in window ? new AbortController() : null;
      var limite = setTimeout(function () { if (controle) controle.abort(); }, 6000);
      fetch('https://viacep.com.br/ws/' + digitos + '/json/', controle ? { signal: controle.signal } : {})
        .then(function (r) { if (!r.ok) throw new Error('http'); return r.json(); })
        .then(function (d) {
          clearTimeout(limite);
          if (digitos !== ultimo) return; // a pessoa já trocou o CEP
          if (d.erro) {
            avisar('Não achamos esse CEP. Confira o número ou preencha o endereço abaixo.', true);
            return;
          }
          if (d.logradouro) campos.logradouro.value = d.logradouro;
          if (d.bairro) campos.bairro.value = d.bairro;
          if (d.localidade) campos.cidade.value = d.localidade;
          if (d.uf) campos.uf.value = d.uf;
          // CEP de cidade pequena não traz rua: aí o cursor vai para a rua, senão direto para o número
          var proximo = d.logradouro ? numero : campos.logradouro;
          avisar(d.logradouro ? 'Endereço encontrado. Agora é só o número e o complemento.'
                              : 'Achamos a cidade. Complete a rua e o número.');
          if (proximo) proximo.focus();
        })
        .catch(function () {
          clearTimeout(limite);
          if (digitos === ultimo) avisar('Não deu para buscar o CEP agora. Preencha o endereço abaixo.', true);
        });
    }
  }

  function carrossel(banner) {
    var slides = banner.querySelectorAll('.slide');
    var numero = document.getElementById('slide-atual');
    var barra = banner.querySelector('.progresso span');
    var botaoPausa = banner.querySelector('.pausar');
    if (slides.length < 2 || !barra || !botaoPausa) return;
    var atual = 0, pausado = reduzir, timer = null;

    // Slides 2 e 3 só baixam a foto quando forem aparecer (economiza dados no celular)
    function carregar(slide) {
      slide.querySelectorAll('[data-srcset]').forEach(function (el) {
        el.srcset = el.dataset.srcset; el.removeAttribute('data-srcset');
      });
      var img = slide.querySelector('img[data-src]');
      if (img) { img.src = img.dataset.src; img.removeAttribute('data-src'); }
    }
    function reiniciarBarra() {
      barra.classList.remove('rodando');
      void barra.offsetWidth; // força o navegador a recomeçar a animação
      if (!pausado) barra.classList.add('rodando');
    }
    function agendar() {
      clearTimeout(timer);
      reiniciarBarra();
      if (!pausado) timer = setTimeout(function () { ir(atual + 1); }, 6000);
    }
    function ir(n) {
      slides[atual].classList.remove('ativo');
      slides[atual].setAttribute('aria-hidden', 'true');
      atual = (n + slides.length) % slides.length;
      carregar(slides[atual]);
      carregar(slides[(atual + 1) % slides.length]); // pré-carrega a próxima
      slides[atual].classList.add('ativo');
      slides[atual].removeAttribute('aria-hidden');
      if (numero) numero.textContent = '0' + (atual + 1);
      agendar();
    }
    function definirPausa(p) {
      pausado = p;
      botaoPausa.textContent = p ? 'Continuar' : 'Pausar';
      botaoPausa.setAttribute('aria-pressed', String(p));
      agendar();
    }

    banner.querySelectorAll('.seta').forEach(function (b) {
      b.addEventListener('click', function () { ir(atual + Number(b.dataset.dir)); });
    });
    botaoPausa.addEventListener('click', function () { definirPausa(!pausado); });
    if (reduzir) definirPausa(true);

    // Deslizar no celular troca a foto (só gesto horizontal claro)
    var x0 = null, y0 = null;
    banner.addEventListener('touchstart', function (e) {
      x0 = e.touches[0].clientX; y0 = e.touches[0].clientY;
    }, { passive: true });
    banner.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.4) ir(atual + (dx < 0 ? 1 : -1));
      x0 = null;
    }, { passive: true });

    // Não gasta animação com a aba escondida
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) clearTimeout(timer); else agendar();
    });

    carregar(slides[1]);
    agendar();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
