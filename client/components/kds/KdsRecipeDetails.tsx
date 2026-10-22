import { AlertTriangle, ClipboardList, Scale } from "lucide-react";
import type { RecipeCompositionIngredient, RecipeCompositionPreview } from "@/lib/api";

function IngredientList({ items }: { items: RecipeCompositionIngredient[] }) {
  if (items.length === 0) return <p className="text-xs text-stone">Nenhum insumo definido.</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((item, index) => (
        <li key={`${item.inventory_item_id}-${item.recipe_version_id ?? "current"}-${index}`} className="flex items-baseline justify-between gap-3 text-sm">
          <span className="min-w-0 truncate">{item.name}</span>
          <strong className="shrink-0 text-gold">{item.quantity} {item.unit_symbol ?? item.unit_id ?? ""}</strong>
        </li>
      ))}
    </ul>
  );
}

function MethodList({ recipe }: { recipe: RecipeCompositionPreview }) {
  const methods = recipe.methods.filter((method) => method.instructions || method.preparation_steps.length > 0);
  if (methods.length === 0) return <p className="text-xs text-stone">Sem instruções adicionais cadastradas.</p>;
  return (
    <div className="space-y-3">
      {methods.map((method) => (
        <div key={method.recipe_version_id} className="space-y-1.5 text-sm">
          {method.instructions && <p className="whitespace-pre-wrap text-stone">{method.instructions}</p>}
          {method.preparation_steps.length > 0 && (
            <ol className="list-inside list-decimal space-y-1 text-stone">
              {method.preparation_steps.map((step, index) => <li key={`${method.recipe_version_id}-${index}`}>{step}</li>)}
            </ol>
          )}
        </div>
      ))}
    </div>
  );
}

export default function KdsRecipeDetails({ recipe }: { recipe: RecipeCompositionPreview | null | undefined }) {
  if (!recipe) {
    return <p className="rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5 p-3 text-xs text-amber-200">Ficha técnica ainda não disponível para este item.</p>;
  }

  return (
    <section className="space-y-3 rounded-xl border border-gold/30 bg-surface-01/80 p-3" aria-label="Ficha técnica do item">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-black text-gold"><Scale size={16} aria-hidden="true" /> Ficha técnica</h3>
        <span className={recipe.complete ? "text-xs font-bold text-emerald-300" : "text-xs font-bold text-amber-300"}>{recipe.complete ? "Completa" : "Pendente"}</span>
      </div>
      {!recipe.complete && recipe.missing.length > 0 && (
        <p className="flex gap-2 rounded-lg bg-amber-500/10 p-2 text-xs text-amber-200"><AlertTriangle size={15} className="shrink-0" aria-hidden="true" /> Faltando: {recipe.missing.join(", ")}</p>
      )}
      <div className="space-y-2 border-t border-surface-03 pt-2">
        <h4 className="text-xs font-black uppercase tracking-wide text-stone">Componentes comuns</h4>
        <IngredientList items={recipe.common_components} />
      </div>
      {recipe.flavors.map((flavor) => (
        <div key={`${flavor.product_id}-${flavor.fraction}`} className="space-y-2 border-t border-surface-03 pt-2">
          <h4 className="text-xs font-black uppercase tracking-wide text-stone">{flavor.name} · fração {flavor.fraction}</h4>
          <IngredientList items={flavor.ingredients} />
        </div>
      ))}
      <div className="space-y-2 border-t border-surface-03 pt-2">
        <h4 className="text-xs font-black uppercase tracking-wide text-stone">Total de insumos</h4>
        <IngredientList items={recipe.ingredients} />
      </div>
      {recipe.removed_ingredients.length > 0 && (
        <div className="space-y-2 border-t border-surface-03 pt-2 text-amber-200">
          <h4 className="text-xs font-black uppercase tracking-wide">Retirados</h4>
          <IngredientList items={recipe.removed_ingredients} />
        </div>
      )}
      <div className="space-y-2 border-t border-surface-03 pt-2">
        <h4 className="flex items-center gap-2 text-xs font-black uppercase tracking-wide text-stone"><ClipboardList size={14} aria-hidden="true" /> Montagem e preparo</h4>
        <MethodList recipe={recipe} />
      </div>
    </section>
  );
}
