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
print(stats)

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

Vill du att jag utvecklar kodmallar för något eller flera av dessa steg direkt? Eller vill du börja själv och komma tillbaka med frågor/problem?
