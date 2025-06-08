# TODO AP7a+AP3a steg 4

Utmärkt, du har nu en stabil grund och tydliga nästa steg. Med AP7 och AP3a steg 4 i fokus kan vi konkretisera arbetsgången så att du får **både en “matchningsdemo” och tillhörande analys/statistik** – hela loopen från simulering till analys och visualisering. Det gör projektet snabbt mer forskningsmässigt intressant och ger dig material att visa upp eller börja skriva om.

### **Konkret arbetsplan för AP7 + AP3a steg 4**

Här är ett konkret förslag, uppdelat i tydliga delmoment (du kan självklart anpassa efter behov):

---

#### **AP7. Matchning & Statisk Simulering**

**a) Grundläggande matchning och visualisering**

1. **Implementera enkel matchningsfunktion**

   * Börja med 1:1 random eller geografisk matchning mellan *Workers* och *Jobs* inom Falun.
   * Spara matchningsresultat (t.ex. worker\_id → job\_id).

2. **Demo 1: Visualisering av grundläggande matchning**

   * Plotta Falun-kartan med:

     * *Bostäder* (residences)
     * *Arbetsplatser* (workplaces)
     * *Pendlingslinjer* mellan hem och jobb för matchade agenter
   * Färgkoda arbetsplatser: **grön = tillsatt**, **röd = vakant**.

3. **Beräkna och skriv ut grundläggande statistik**

   * Totalt antal arbetssökande, antal jobb, antal matchade, antal arbetslösa, antal lediga jobb.
   * Antal pendlare per arbetsplats.
   * Enkel summering: “X% matchade, Y% arbetslösa”.

---

**b) Egenskapsbaserad matchning**
4\. **Utveckla och implementera utility-funktion baserad på occupation space**

* Allokera arbetare till jobb baserat på närhet i (chi, xi) eller valfri kompetensvektor.
* Jämför utfall med random/geografisk matchning.

5. **Demo 2: Visualisering av egenskapsmatchning**

   * Samma karta, men färgkoda nu även efter cluster/occupation om du vill.
   * Plotta jämförande statistik: hur förändras fördelning av arbetslöshet, pendlingsavstånd etc.

---

#### **AP3a steg 4. Analys och statistik**

1. **Beräkna och visualisera:**

   * **Antal pendlare per arbetsplats** (histogram eller stapeldiagram)
   * **Arbetslöshet per område/kluster** (bar chart, heatmap, karta)
   * **Geografisk klustring** (enkel spatial analys, ev. heatmap)
   * **Pendlingsavstånd** (kanske ett histogram eller medelvärde per område)
   * **Demo:** Sammanställ och visa summeringar, gärna både som tabell och karta.

2. **Dokumentera utfall**

   * En enkel rapport (kan vara i Markdown) med:

     * Vilken matchningslogik som använts
     * Nyckeltal och tabeller
     * Skärmdumpar/plots från demo

---

### **Kodmall för demo (första version)**

Vill du ha en kodmall för första demot (random matchning, statistik, plottning för Falun)?
Den kan se ut så här i grova drag (pseudo-Python):

```python
# Steg 1: Matchning
matched = match_workers_to_jobs_random(workers, jobs)

# Steg 2: Plottning
plot_matching_on_map(workers, jobs, matched, kommun_polygon)

# Steg 3: Statistik
stats = compute_matching_stats(workers, jobs, matched)
log(stats)

# Steg 4: Demo/rapport
save_demo_results(stats, "falun_random_demo.md")
```

Du kan sedan utveckla motsvarande för occupation space-matching genom att byta ut matchningsfunktionen och ev. lägga till utility-kalkyl.

Vill du ha denna kodmall (eller en mer utförlig version) direkt, eller vill du börja själv och återkomma när du kört fast?
 
-

### **Förslag på TODO/arbetslista att checka av**

1. [ ] Implementera random/geografisk matchning
2. [ ] Plotta Falun-kartan med resultat (matchade/vakanta jobb)
3. [ ] Beräkna och skriv ut statistik (matchade, arbetslösa, lediga jobb, pendlingsavstånd)
4. [ ] Implementera occupation space-matchning
5. [ ] Plotta och jämför utfall mot random (samma statistik/plots)
6. [ ] Visualisera och sammanställ resultat (tabell + diagram + kartor)
7. [ ] Dokumentera demokörningarna (t.ex. README/demo.md)

---

# FORTSÄTTNING 2025-06-07

Här är **att-göra-listan sorterad efter förväntad “payoff”** – alltså vad som snabbast ger nytta, insikt och vidare fart i utvecklingen av projektet. Jag har delat upp den i fyra prio-grupper och tagit hänsyn till beroenden. Säg till om du vill ha ännu tuffare prioritering!

---

## **A. Hög payoff, direkt effekt**

1. **Multi-kommun-stöd i config och i kod**

   * Möjliggör både generella och kommun-specifika parametrar i YAML för t.ex. utbildningsnivåer, workforce\_ratio, befolkning.
   * Läs in befolkning och arbetskraft från databas där det saknas i config.
   * Se till att arbetsgivare, jobb och workers genereras separat för varje kommun med rätt parametrar.
2. **Inför workforce participation rate (`workforce_ratio`) och använd för att beräkna antal workers automatiskt från befolkning.**
3. **Utöka statistik och kontrollutskrifter/rapporter:**

   * Fördelning arbetsgivare, jobb, arbetskraft och arbetsmarknadsstatus per kommun.
   * Utskrift av nyckeltal vid generering.
4. **Robust hantering av saknade data och fallback i config/databas.**
5. **Kommentera/refaktorera kodbasen kring scenariohantering och arbetsgivargenerering där det behövs för tydlighet.**

---

## **B. Nästa steg – visualisering, analys, riktiga data**

6. **Utöka plottingfunktionerna:**

   * Möjlighet att plocka fram arbetsgivare, workers och ev. pendlingsflöden på karta.
   * Kontrollera och förbättra stöd för flera kommuner i både generering och plotting.
7. **Lägg in och testa nya tabeller (pendlingsströmmar, arbetsmarknadsstatus, ev. vatten) separat i databasen.**
8. **Smart filtrering i kartdata (t.ex. exkludera vatten) för bättre visualisering och analyser.**
9. **Uppdatera README och TODO med nuvarande arbetsflöde, tips, typfall.**

---

## **C. Teoretisk och modellutveckling**

10. **Koppling SNI ↔ O\*NET/occupation space:**

    * Skapa pipeline/mappning SNI–>O\*NET och lagra xi/chi för arbetsgivare/yrken i arbetsgivartabellen.
    * Börja visualisera företag (och/eller individer) i occupation space, och visa exempel på klustring/matchning.
    * Fundera över och ev. implementera spridning på xi/chi för jobb inom samma arbetsgivare.
11. **Implementera arbetsmarknadsstatus (sysselsatt, arbetslös etc) som fördelning i workers/jobbgenerering.**

---

## **D. Avancerad funktionalitet och framtida utveckling**

12. **Förbered händelsedriven simulering (event queue) med dag som minsta tidsenhet, och logik för eventgenerering.**
13. **Utöka modellen för att simulera och matcha pendlingsflöden mellan kommuner (använd tabellerna för pendling).**
14. **Utveckla/parametrisera tidsberoende parametrar och scenario över flera år i YAML och kod.**

---

Vill du ha ett konkret “nästa steg” för direkt kodande, eller ska vi formulera YAML och default-laddning av data för fler kommuner först?
