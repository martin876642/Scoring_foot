/* FootScout — données joueur (simule players.json exporté depuis Python)
   Toutes les valeurs de scoring sont des percentiles 0–100 normalisés par groupe de poste. */

const PLAYER = {
  id: "ferreira-mateo",
  nom: "Mateo Ferreira",
  club: { nom: "Stade Atlantique", abbr: "STA", couleur: "#c0392b" },
  ligue: "Ligue 1",
  age: 23,
  taille: 186,
  pied: "Droit",
  nationalite: { code: "BRA", nom: "Brésil" },
  poste: "Avant-centre",
  posteAbbr: "CF",
  valeur: "124",          // M€
  contrat: "30/06/2027",

  // Bande de stats rapides — saison en cours
  statsRapides: [
    { label: "Matchs joués", valeur: "31" },
    { label: "Min / match", valeur: "84" },
    { label: "Buts", valeur: "22" },
    { label: "Passes déc.", valeur: "9" },
    { label: "xG", valeur: "19.4" },
    { label: "xA", valeur: "6.8" },
  ],

  // Scores par rôle — poste principal (CF)
  rolesPrincipaux: [
    {
      id: "profondeur", nom: "Profondeur", score: 94, rang: "#1 Ligue 1",
      features: [
        { label: "Courses en prof.", v: 95 },
        { label: "Buts /90", v: 96 },
        { label: "npxG /90", v: 92 },
        { label: "Vitesse max", v: 90 },
        { label: "Touches surface", v: 88 },
        { label: "Conversion %", v: 88 },
      ],
    },
    {
      id: "renard", nom: "Renard des surfaces", score: 91, rang: "#1 Ligue 1",
      features: [
        { label: "Buts /90", v: 96 },
        { label: "npxG /90", v: 92 },
        { label: "Touches surface", v: 89 },
        { label: "Conversion %", v: 88 },
        { label: "Positionnement", v: 93 },
        { label: "Tirs /90", v: 70 },
      ],
    },
    {
      id: "pressing", nom: "Attaquant de pressing", score: 78, rang: "#5 Big 5",
      features: [
        { label: "Pressings /90", v: 77 },
        { label: "Impact PPDA", v: 80 },
        { label: "Récup. hautes", v: 74 },
        { label: "Intensité", v: 82 },
        { label: "Duels off.", v: 60 },
        { label: "Distance /90", v: 55 },
      ],
    },
    {
      id: "faux9", nom: "Faux 9", score: 63, rang: "#14 Big 5",
      features: [
        { label: "xGBuildup", v: 66 },
        { label: "xA", v: 64 },
        { label: "xGChain", v: 70 },
        { label: "Passes clés", v: 58 },
        { label: "Touches", v: 61 },
        { label: "npxG", v: 92 },
        { label: "Dribbles %", v: 81 },
      ],
    },
    {
      id: "pivot", nom: "Pivot", score: 41, rang: "#38 Big 5",
      features: [
        { label: "Duels aériens %", v: 47 },
        { label: "Buts de tête", v: 67 },
        { label: "Touches", v: 61 },
        { label: "Duels %", v: 38 },
        { label: "Pertes balle (inv.)", v: 30 },
        { label: "Fautes subies", v: 52 },
      ],
    },
  ],

  // Poste secondaire (W — ailier)
  posteSecondaire: "Ailier",
  posteSecondaireAbbr: "W",
  rolesSecondaires: [
    {
      id: "ailier-int", nom: "Ailier intérieur", score: 82, rang: "#3 Ligue 1",
      features: [
        { label: "Dribbles %", v: 81 },
        { label: "Buts /90", v: 88 },
        { label: "xA", v: 64 },
        { label: "Passes clés", v: 58 },
        { label: "Courses prof.", v: 86 },
        { label: "Tirs /90", v: 75 },
      ],
    },
    {
      id: "ailier-deb", nom: "Ailier débordant", score: 58, rang: "#21 Big 5",
      features: [
        { label: "Centres réussis %", v: 50 },
        { label: "Dribbles %", v: 81 },
        { label: "Sprints /90", v: 84 },
        { label: "Passes clés", v: 58 },
        { label: "xA", v: 64 },
        { label: "Débordements", v: 55 },
      ],
    },
  ],

  // Profils similaires
  similaires: [
    { nom: "Julian Köhler", club: "RB Westfalen", sim: 91 },
    { nom: "Tomás Vidal", club: "Real Cantábrico", sim: 88 },
    { nom: "Aymen Belkacem", club: "Olympique Riviera", sim: 85 },
  ],

  // Stats détaillées — percentiles + valeur brute (tooltip)
  statsDetaillees: [
    {
      titre: "Finition",
      stats: [
        { label: "Buts (hors pen.) /90", p: 96, brut: "0.71 /90" },
        { label: "npxG /90", p: 92, brut: "0.62 /90" },
        { label: "Taux de conversion", p: 88, brut: "24 %" },
        { label: "Tirs cadrés %", p: 74, brut: "48 %" },
        { label: "Buts de la tête", p: 67, brut: "5 cette saison" },
      ],
    },
    {
      titre: "Création",
      stats: [
        { label: "Dribbles réussis %", p: 81, brut: "61 %" },
        { label: "Passes décisives /90", p: 71, brut: "0.29 /90" },
        { label: "xA /90", p: 64, brut: "0.22 /90" },
        { label: "Passes clés /90", p: 58, brut: "1.4 /90" },
        { label: "Passes progressives /90", p: 49, brut: "3.1 /90" },
      ],
    },
    {
      titre: "Défensif",
      stats: [
        { label: "Pressings /90", p: 77, brut: "19.2 /90" },
        { label: "Récupérations /90", p: 42, brut: "3.0 /90" },
        { label: "Duels déf. gagnés %", p: 35, brut: "41 %" },
        { label: "Interceptions /90", p: 22, brut: "0.4 /90" },
        { label: "Tacles /90", p: 18, brut: "0.3 /90" },
      ],
    },
    {
      titre: "Physique",
      stats: [
        { label: "Vitesse max", p: 90, brut: "34.6 km/h" },
        { label: "Sprints /90", p: 84, brut: "32 /90" },
        { label: "Accélérations /90", p: 79, brut: "26 /90" },
        { label: "Distance /90", p: 55, brut: "10.4 km" },
        { label: "Duels aériens gagnés %", p: 47, brut: "52 %" },
      ],
    },
  ],
};
