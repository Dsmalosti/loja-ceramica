// Menu do celular: abre/fecha pelo botão e fecha com Esc.
// Melhoria progressiva: sem este arquivo, o menu fica sempre visível.
document.addEventListener('DOMContentLoaded', function () {
  var topo = document.querySelector('.topo');
  if (!topo) return;
  var botao = topo.querySelector('.topo__botao');
  topo.classList.add('topo--js');
  botao.hidden = false;

  function alternar(abrir) {
    topo.classList.toggle('topo--aberto', abrir);
    botao.setAttribute('aria-expanded', String(abrir));
  }
  botao.addEventListener('click', function () {
    alternar(botao.getAttribute('aria-expanded') !== 'true');
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') alternar(false);
  });
});
