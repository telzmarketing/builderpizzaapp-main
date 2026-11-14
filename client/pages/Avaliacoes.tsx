import { useEffect, useState } from "react";
import { ChevronLeft, Star } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { reviewsApi, type ApiCustomerReview } from "@/lib/api";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

export default function Avaliacoes() {
  const navigate = useNavigate();
  const [reviews, setReviews] = useState<ApiCustomerReview[]>([]);
  useEffect(() => { reviewsApi.listPublic().then(setReviews).catch(() => setReviews([])); }, []);
  return <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 pb-24">
    <header className="bg-brand-dark px-4 py-3 flex items-center justify-between sticky top-0 z-30">
      <button onClick={() => navigate(-1)} aria-label="Voltar" className="text-parchment"><ChevronLeft size={24} /></button>
      <MoschettieriLogo className="text-cream text-base scale-[1.15]" />
      <span className="w-6" />
    </header>
    <main className="max-w-2xl mx-auto px-4 py-6">
      <h1 className="text-cream text-2xl font-bold">Avaliações de clientes</h1>
      <p className="text-stone text-sm mt-1">Veja o que nossos clientes acharam dos pedidos e pizzas.</p>
      <div className="mt-6 space-y-3">
        {reviews.map((review) => <article key={review.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
          <div className="flex items-center justify-between gap-3"><span className="text-cream font-semibold">{review.author_name || "Cliente"}</span><div className="flex items-center gap-0.5 text-gold">{[1,2,3,4,5].map((star) => <Star key={star} size={15} className={star <= review.rating ? "fill-gold" : "text-stone/40"} />)}</div></div>
          {review.comment && <p className="text-parchment text-sm mt-2">{review.comment}</p>}
          {review.product_name && <p className="text-stone text-xs mt-2">Sobre: {review.product_name}</p>}
        </article>)}
        {reviews.length === 0 && <p className="text-stone text-sm text-center py-12">Ainda não há avaliações publicadas.</p>}
      </div>
    </main>
    <BottomNav />
  </div>;
}
