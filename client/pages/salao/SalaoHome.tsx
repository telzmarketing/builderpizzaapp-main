import { useEffect, useState } from "react";
import { CalendarDays, Clock, Loader2, MapPin, Phone, Utensils } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { productsApi, resolveAssetUrl, salaoApi, salaoPageApi, type ApiProduct, type ApiSalaoPageSettings } from "@/lib/api";

const DEFAULT_PAGE: ApiSalaoPageSettings = {
  id: "default",
  enabled: true,
  hero_eyebrow: "Restaurante italiano em Sao Paulo",
  hero_title: "Moschettieri",
  hero_subtitle: "pizza, sala e experiencia.",
  hero_description: "Uma pagina institucional para o salao, reservas e apresentacao premium do restaurante, separada da loja delivery e integrada ao mesmo ecossistema.",
  primary_cta_label: "Reservar mesa",
  secondary_cta_label: "Ver cardapio",
  hero_background_image: "/salao/hero-ambience.jpg",
  hero_plate_image: "/salao/hero-plate.png",
  experience_eyebrow: "A casa",
  experience_title: "Uma experiencia pensada para o salao.",
  experience_text: "O canal do salao nasce separado da loja delivery: outro visual, outra navegacao e outro objetivo comercial, mantendo o mesmo ERP, CRM, BI e base operacional.",
  experience_cards: [
    {
      title: "Ambiente acolhedor",
      text: "Uma casa italiana para jantar com calma, vinho na mesa e atendimento presente.",
      image: "/salao/experience-01.jpg",
    },
    {
      title: "Forno, massa e tradicao",
      text: "Receitas feitas para valorizar a pizza servida no salao, com textura, aroma e tempo certo.",
      image: "/salao/experience-02.jpg",
    },
  ],
  menu_eyebrow: "Cardapio do salao",
  menu_title: "Destaques da mesa.",
  menu_items: [
    { name: "Pizza Marguerita", description: "Disponivel para composicao do cardapio institucional do salao." },
    { name: "Pizza Portuguesa", description: "Disponivel para composicao do cardapio institucional do salao." },
    { name: "Pizza Quatro Queijos", description: "Disponivel para composicao do cardapio institucional do salao." },
    { name: "Pizza Calabresa", description: "Disponivel para composicao do cardapio institucional do salao." },
  ],
  reservation_eyebrow: "Reservas",
  reservation_title: "Reserve sua mesa.",
  reservation_text: "Solicite sua reserva online. A equipe confirma disponibilidade e horario pelo canal de contato informado.",
  reservation_background_image: "/salao/reservation.jpg",
  address: "Santana, Sao Paulo - SP",
  hours: "Funcionamento configuravel pelo modulo Pagina Salao.",
  phone: "Contato e WhatsApp integrados ao ecossistema.",
  whatsapp_url: "",
  seo_title: "Moschettieri | Restaurante",
  seo_description: "Restaurante Moschettieri: experiencia premium de salao, cardapio institucional e reservas online.",
};

export default function SalaoHome() {
  const [page, setPage] = useState<ApiSalaoPageSettings>(DEFAULT_PAGE);
  const [salaoProducts, setSalaoProducts] = useState<ApiProduct[]>([]);
  const [reservation, setReservation] = useState({
    customer_name: "",
    customer_phone: "",
    customer_email: "",
    reservation_date: "",
    reservation_time: "",
    guests_count: "2",
    notes: "",
  });
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    salaoPageApi.get().then((config) => setPage({ ...DEFAULT_PAGE, ...config })).catch(() => {});
    productsApi.list(true, undefined, "dine_in")
      .then((items) => setSalaoProducts(items.filter((item) => item.visible_dine_in !== false)))
      .catch(() => setSalaoProducts([]));
  }, []);

  useEffect(() => {
    document.title = page.seo_title || DEFAULT_PAGE.seo_title;
    const meta = document.querySelector<HTMLMetaElement>("meta[name='description']") ?? document.createElement("meta");
    meta.name = "description";
    meta.content = page.seo_description || DEFAULT_PAGE.seo_description;
    if (!meta.parentElement) document.head.appendChild(meta);
  }, [page.seo_title, page.seo_description]);

  const handleReservation = async () => {
    setFeedback("");
    if (!reservation.customer_name || !reservation.customer_phone || !reservation.reservation_date || !reservation.reservation_time) {
      setFeedback("Preencha nome, telefone, data e horario.");
      return;
    }
    setSending(true);
    try {
      await salaoApi.reservations.publicCreate({
        customer_name: reservation.customer_name,
        customer_phone: reservation.customer_phone,
        customer_email: reservation.customer_email || null,
        reservation_date: reservation.reservation_date,
        reservation_time: reservation.reservation_time,
        guests_count: Math.max(1, Number(reservation.guests_count) || 1),
        notes: reservation.notes || null,
      });
      setFeedback("Reserva recebida. Nossa equipe vai confirmar o horario.");
      setReservation({
        customer_name: "",
        customer_phone: "",
        customer_email: "",
        reservation_date: "",
        reservation_time: "",
        guests_count: "2",
        notes: "",
      });
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Nao foi possivel solicitar a reserva agora.");
    } finally {
      setSending(false);
    }
  };

  if (!page.enabled) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#0b0906] px-5 text-center text-[#f8efe0]">
        <div>
          <MoschettieriLogo className="mx-auto h-14 text-[44px] text-[#d7af63]" />
          <p className="mt-6 text-sm uppercase tracking-[0.26em] text-[#d7af63]">Restaurante Moschettieri</p>
          <h1 className="mt-3 text-4xl font-semibold">Pagina temporariamente indisponivel.</h1>
        </div>
      </main>
    );
  }

  const menuRows = salaoProducts.length > 0
    ? salaoProducts.map((product) => ({
        key: product.id,
        name: product.name,
        description: product.description,
        price: product.dine_in_price ?? product.current_price ?? product.price,
      }))
    : page.menu_items.map((item) => ({
        key: item.name,
        name: item.name,
        description: item.description,
        price: null as number | null,
      }));

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#0b0906] text-[#f8efe0]">
      <section className="relative min-h-screen isolate">
        <img
          src={resolveAssetUrl(page.hero_background_image)}
          alt="Ambiente do restaurante Moschettieri"
          className="absolute inset-0 h-full w-full object-cover opacity-45"
        />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_72%_18%,rgba(190,136,68,0.22),transparent_34%),linear-gradient(90deg,rgba(11,9,6,0.96),rgba(11,9,6,0.76)_45%,rgba(11,9,6,0.5))]" />

        <header className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-10">
          <a href="/" aria-label="Moschettieri restaurante">
            <MoschettieriLogo className="h-12 text-[38px] text-[#d7af63] sm:h-14 sm:text-[46px]" />
          </a>
          <nav className="hidden items-center gap-8 text-xs font-semibold uppercase tracking-[0.24em] text-[#f5dfb3]/80 md:flex">
            <a className="transition hover:text-[#d7af63]" href="#experiencia">Experiencia</a>
            <a className="transition hover:text-[#d7af63]" href="#cardapio">Cardapio</a>
            <a className="transition hover:text-[#d7af63]" href="#reservas">Reservas</a>
            <a className="transition hover:text-[#d7af63]" href="#contato">Contato</a>
          </nav>
          <a
            href="#reservas"
            className="inline-flex h-10 items-center gap-2 rounded-full border border-[#d7af63]/60 px-4 text-xs font-semibold uppercase tracking-[0.18em] text-[#f6dfad] transition hover:bg-[#d7af63] hover:text-[#171008]"
          >
            <CalendarDays className="h-4 w-4" />
            <span className="hidden sm:inline">{page.primary_cta_label}</span>
          </a>
        </header>

        <div className="relative z-10 mx-auto grid min-h-[calc(100vh-92px)] w-full max-w-7xl items-center gap-10 px-5 pb-16 pt-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(320px,520px)] lg:px-10">
          <div className="max-w-3xl">
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.34em] text-[#d7af63]">
              {page.hero_eyebrow}
            </p>
            <h1
              className="max-w-4xl text-[clamp(3rem,8vw,8.5rem)] font-semibold leading-[0.86] text-[#fff7e7]"
              style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
            >
              {page.hero_title}
            </h1>
            <p
              className="mt-4 max-w-2xl text-[clamp(1.6rem,3vw,3rem)] italic leading-tight text-[#d7af63]"
              style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
            >
              {page.hero_subtitle}
            </p>
            <p className="mt-8 max-w-xl text-sm leading-7 text-[#f8efe0]/75 sm:text-base">
              {page.hero_description}
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <a
                href="#reservas"
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-[#d7af63] px-6 text-sm font-bold uppercase tracking-[0.16em] text-[#171008] transition hover:bg-[#f5d083]"
              >
                <CalendarDays className="h-4 w-4" />
                {page.primary_cta_label}
              </a>
              <a
                href="#cardapio"
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full border border-[#f8efe0]/25 px-6 text-sm font-bold uppercase tracking-[0.16em] text-[#f8efe0] transition hover:border-[#d7af63] hover:text-[#d7af63]"
              >
                <Utensils className="h-4 w-4" />
                {page.secondary_cta_label}
              </a>
            </div>
          </div>

          <div className="relative mx-auto hidden w-full max-w-[480px] lg:block">
            <div className="absolute -inset-8 rounded-full bg-[#d7af63]/10 blur-3xl" />
            <img
              src={resolveAssetUrl(page.hero_plate_image)}
              alt="Prato em destaque do restaurante"
              className="relative mx-auto aspect-square w-full object-contain drop-shadow-[0_30px_70px_rgba(0,0,0,0.55)]"
            />
          </div>
        </div>
      </section>

      <section id="experiencia" className="bg-[#120d08] px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.34em] text-[#d7af63]">{page.experience_eyebrow}</p>
            <h2
              className="mt-4 text-4xl font-semibold leading-none text-[#fff7e7] sm:text-6xl"
              style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
            >
              {page.experience_title}
            </h2>
          </div>
          <p className="max-w-2xl text-sm leading-7 text-[#f8efe0]/70 sm:text-base">
            {page.experience_text}
          </p>
        </div>

        <div className="mx-auto mt-10 grid max-w-7xl gap-5 md:grid-cols-2">
          {page.experience_cards.map((card) => (
            <article key={card.title} className="overflow-hidden rounded-[2px] border border-[#d7af63]/16 bg-[#1a120b]">
              <img src={resolveAssetUrl(card.image)} alt={card.title} className="h-72 w-full object-cover" />
              <div className="p-6 sm:p-8">
                <h3
                  className="text-3xl font-semibold text-[#fff7e7]"
                  style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
                >
                  {card.title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-[#f8efe0]/68">{card.text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="cardapio" className="bg-[#0b0906] px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.34em] text-[#d7af63]">{page.menu_eyebrow}</p>
              <h2
                className="mt-4 text-4xl font-semibold leading-none text-[#fff7e7] sm:text-6xl"
                style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
              >
                {page.menu_title}
              </h2>
            </div>
            <a
              href="#reservas"
              className="inline-flex h-11 w-fit items-center justify-center rounded-full border border-[#d7af63]/55 px-5 text-xs font-bold uppercase tracking-[0.18em] text-[#f6dfad] transition hover:bg-[#d7af63] hover:text-[#171008]"
            >
              {page.primary_cta_label}
            </a>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {menuRows.map((item) => (
              <div key={item.key} className="border-y border-[#d7af63]/18 py-6">
                <p className="text-xs uppercase tracking-[0.24em] text-[#d7af63]">Moschettieri</p>
                <h3
                  className="mt-3 text-3xl font-semibold leading-tight text-[#fff7e7]"
                  style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
                >
                  {item.name}
                </h3>
                <p className="mt-3 text-sm leading-6 text-[#f8efe0]/62">
                  {item.description}
                </p>
                {item.price !== null && (
                  <p className="mt-4 text-sm font-bold tracking-[0.16em] text-[#d7af63]">
                    {item.price.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="reservas" className="relative isolate bg-[#120d08] px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <img src={resolveAssetUrl(page.reservation_background_image)} alt="" className="absolute inset-0 h-full w-full object-cover opacity-18" />
        <div className="absolute inset-0 bg-[#120d08]/82" />
        <div className="relative mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.34em] text-[#d7af63]">{page.reservation_eyebrow}</p>
            <h2
              className="mt-4 text-4xl font-semibold leading-none text-[#fff7e7] sm:text-6xl"
              style={{ fontFamily: "'Cormorant Garamond', Georgia, serif" }}
            >
              {page.reservation_title}
            </h2>
            <p className="mt-5 max-w-xl text-sm leading-7 text-[#f8efe0]/70 sm:text-base">
              {page.reservation_text}
            </p>
          </div>

          <form className="grid gap-4 rounded-[2px] border border-[#d7af63]/20 bg-[#0b0906]/82 p-5 sm:grid-cols-2 sm:p-7">
            <input value={reservation.customer_name} onChange={(event) => setReservation((prev) => ({ ...prev, customer_name: event.target.value }))} className="h-12 rounded-[2px] border border-[#d7af63]/18 bg-[#1a120b] px-4 text-sm outline-none placeholder:text-[#f8efe0]/35 focus:border-[#d7af63]" placeholder="Nome" />
            <input value={reservation.customer_phone} onChange={(event) => setReservation((prev) => ({ ...prev, customer_phone: event.target.value }))} className="h-12 rounded-[2px] border border-[#d7af63]/18 bg-[#1a120b] px-4 text-sm outline-none placeholder:text-[#f8efe0]/35 focus:border-[#d7af63]" placeholder="Telefone" />
            <input value={reservation.customer_email} onChange={(event) => setReservation((prev) => ({ ...prev, customer_email: event.target.value }))} className="h-12 rounded-[2px] border border-[#d7af63]/18 bg-[#1a120b] px-4 text-sm outline-none placeholder:text-[#f8efe0]/35 focus:border-[#d7af63]" placeholder="Email" />
            <input type="date" value={reservation.reservation_date} onChange={(event) => setReservation((prev) => ({ ...prev, reservation_date: event.target.value }))} className="h-12 rounded-[2px] border border-[#d7af63]/18 bg-[#1a120b] px-4 text-sm outline-none placeholder:text-[#f8efe0]/35 focus:border-[#d7af63]" />
            <input type="time" value={reservation.reservation_time} onChange={(event) => setReservation((prev) => ({ ...prev, reservation_time: event.target.value }))} className="h-12 rounded-[2px] border border-[#d7af63]/18 bg-[#1a120b] px-4 text-sm outline-none placeholder:text-[#f8efe0]/35 focus:border-[#d7af63]" />
            <input type="number" min="1" value={reservation.guests_count} onChange={(event) => setReservation((prev) => ({ ...prev, guests_count: event.target.value }))} className="h-12 rounded-[2px] border border-[#d7af63]/18 bg-[#1a120b] px-4 text-sm outline-none placeholder:text-[#f8efe0]/35 focus:border-[#d7af63]" placeholder="Pessoas" />
            <textarea value={reservation.notes} onChange={(event) => setReservation((prev) => ({ ...prev, notes: event.target.value }))} className="min-h-24 rounded-[2px] border border-[#d7af63]/18 bg-[#1a120b] px-4 py-3 text-sm outline-none placeholder:text-[#f8efe0]/35 focus:border-[#d7af63] sm:col-span-2" placeholder="Observacoes" />
            <button
              type="button"
              onClick={handleReservation}
              disabled={sending}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-[#d7af63] px-6 text-sm font-bold uppercase tracking-[0.16em] text-[#171008] transition hover:bg-[#f5d083] sm:col-span-2"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
              {sending ? "Enviando..." : "Solicitar reserva"}
            </button>
            {feedback && <p className="text-center text-sm text-[#f8efe0]/72 sm:col-span-2">{feedback}</p>}
          </form>
        </div>
      </section>

      <footer id="contato" className="bg-[#080604] px-5 py-10 sm:px-8 lg:px-10">
        <div className="mx-auto grid max-w-7xl gap-6 border-t border-[#d7af63]/20 pt-8 text-sm text-[#f8efe0]/68 md:grid-cols-3">
          <div className="flex items-start gap-3">
            <MapPin className="mt-0.5 h-4 w-4 text-[#d7af63]" />
            <span>{page.address}</span>
          </div>
          <div className="flex items-start gap-3">
            <Clock className="mt-0.5 h-4 w-4 text-[#d7af63]" />
            <span>{page.hours}</span>
          </div>
          <div className="flex items-start gap-3">
            <Phone className="mt-0.5 h-4 w-4 text-[#d7af63]" />
            {page.whatsapp_url ? <a href={page.whatsapp_url} className="hover:text-[#d7af63]">{page.phone}</a> : <span>{page.phone}</span>}
          </div>
        </div>
      </footer>
    </main>
  );
}
