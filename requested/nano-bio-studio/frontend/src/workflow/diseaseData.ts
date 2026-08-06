/**
 * Disease → subtype → therapeutic taxonomy.
 *
 * GENERATED from the legacy application's authoritative source,
 * `data/disease_drug_mapping.py`, so the React workflow offers exactly the same
 * clinical options as the Streamlit application. Nothing here was invented: no
 * disease, subtype, drug or epidemiology figure was added, removed or edited.
 *
 * Regenerate rather than hand-edit if the Python source changes.
 */

export interface DiseaseSubtype {
  name: string;
  drugs: readonly string[];
}

export interface DiseaseEpidemiology {
  incidence: string | null;
  mortality: string | null;
  fiveYearSurvival: string | null;
}

export interface Disease {
  name: string;
  epidemiology: DiseaseEpidemiology;
  unmetNeeds: string | null;
  subtypes: readonly DiseaseSubtype[];
}

export const DISEASES: readonly Disease[] = [
  {
    "name": "Liver Cancer (HCC)",
    "epidemiology": {
      "incidence": "870,000 new cases annually",
      "mortality": "830,000 deaths annually",
      "fiveYearSurvival": "18%"
    },
    "unmetNeeds": "Early detection, improved response rates, combination therapies",
    "subtypes": [
      {
        "name": "AFP-high HCC",
        "drugs": [
          "Sorafenib",
          "Lenvatinib"
        ]
      },
      {
        "name": "Immune-active HCC",
        "drugs": [
          "Lenvatinib",
          "Atezolizumab + Bevacizumab",
          "Durvalumab",
          "Nivolumab",
          "Pembrolizumab"
        ]
      },
      {
        "name": "Immune-excluded HCC",
        "drugs": [
          "Sorafenib",
          "Lenvatinib",
          "Durvalumab",
          "Pembrolizumab"
        ]
      },
      {
        "name": "Immune-desert HCC",
        "drugs": [
          "Sorafenib",
          "Lenvatinib"
        ]
      }
    ]
  },
  {
    "name": "Pancreatic Cancer",
    "epidemiology": {
      "incidence": "500,000 new cases annually",
      "mortality": "440,000 deaths annually",
      "fiveYearSurvival": "11%"
    },
    "unmetNeeds": "Early detection, immunotherapy combinations, delivery to fibrotic stroma",
    "subtypes": [
      {
        "name": "Ductal Adenocarcinoma",
        "drugs": [
          "Gemcitabine",
          "Abraxane (Albumin-bound Paclitaxel)",
          "FOLFIRINOX",
          "Durvalumab"
        ]
      },
      {
        "name": "Neuroendocrine Tumor",
        "drugs": [
          "Durvalumab",
          "Somatostatin Analogs"
        ]
      },
      {
        "name": "Acinar Cell Carcinoma",
        "drugs": [
          "Gemcitabine",
          "Abraxane (Albumin-bound Paclitaxel)",
          "FOLFIRINOX",
          "Durvalumab",
          "Somatostatin Analogs"
        ]
      }
    ]
  },
  {
    "name": "Breast Cancer",
    "epidemiology": {
      "incidence": "2.2 million new cases annually",
      "mortality": "620,000 deaths annually",
      "fiveYearSurvival": "90%"
    },
    "unmetNeeds": "TNBC treatment, resistance to HER2 therapy, cardiac toxicity mitigation",
    "subtypes": [
      {
        "name": "Luminal A (ER/PR+, HER2-)",
        "drugs": [
          "Tamoxifen",
          "Trastuzumab (Herceptin)",
          "Pertuzumab",
          "Lapatinib",
          "Paclitaxel",
          "Pembrolizumab",
          "Atezolizumab"
        ]
      },
      {
        "name": "Luminal B (ER/PR+, HER2+)",
        "drugs": [
          "Tamoxifen",
          "Trastuzumab (Herceptin)",
          "Pertuzumab",
          "Lapatinib",
          "Paclitaxel",
          "Pembrolizumab",
          "Atezolizumab"
        ]
      },
      {
        "name": "HER2-enriched (ER-, PR-, HER2+)",
        "drugs": [
          "Tamoxifen",
          "Trastuzumab (Herceptin)",
          "Pertuzumab",
          "Lapatinib",
          "Paclitaxel",
          "Pembrolizumab",
          "Atezolizumab"
        ]
      },
      {
        "name": "Triple-Negative (ER-, PR-, HER2-)",
        "drugs": [
          "Tamoxifen",
          "Trastuzumab (Herceptin)",
          "Pertuzumab",
          "Lapatinib",
          "Paclitaxel",
          "Pembrolizumab",
          "Atezolizumab"
        ]
      }
    ]
  },
  {
    "name": "Lung Cancer",
    "epidemiology": {
      "incidence": "2.2 million new cases annually",
      "mortality": "1.8 million deaths annually",
      "fiveYearSurvival": "21% (NSCLC), 7% (SCLC)"
    },
    "unmetNeeds": "Brain metastasis treatment, overcoming resistance, combination therapies",
    "subtypes": [
      {
        "name": "Non-Small Cell Lung Cancer (NSCLC)",
        "drugs": [
          "Pembrolizumab",
          "Nivolumab",
          "Atezolizumab",
          "Pemetrexed"
        ]
      },
      {
        "name": "Small Cell Lung Cancer (SCLC)",
        "drugs": [
          "Nivolumab"
        ]
      },
      {
        "name": "Adenocarcinoma",
        "drugs": [
          "Erlotinib",
          "Gefitinib",
          "Crizotinib"
        ]
      },
      {
        "name": "Squamous Cell Carcinoma",
        "drugs": [
          "Pembrolizumab",
          "Nivolumab",
          "Atezolizumab",
          "Erlotinib",
          "Gefitinib",
          "Crizotinib",
          "Pemetrexed"
        ]
      }
    ]
  },
  {
    "name": "Colorectal Cancer",
    "epidemiology": {
      "incidence": "1.9 million new cases annually",
      "mortality": "935,000 deaths annually",
      "fiveYearSurvival": "65%"
    },
    "unmetNeeds": "Immunotherapy combinations, delivery to colon, metastatic disease treatment",
    "subtypes": [
      {
        "name": "Adenocarcinoma",
        "drugs": [
          "5-Fluorouracil (5-FU)",
          "Oxaliplatin",
          "Cetuximab",
          "Bevacizumab",
          "Irinotecan"
        ]
      },
      {
        "name": "Mucinous Adenocarcinoma",
        "drugs": [
          "5-Fluorouracil (5-FU)",
          "Oxaliplatin",
          "Bevacizumab"
        ]
      },
      {
        "name": "Neuroendocrine Tumor",
        "drugs": [
          "5-Fluorouracil (5-FU)",
          "Oxaliplatin",
          "Cetuximab",
          "Bevacizumab",
          "Pembrolizumab",
          "Nivolumab",
          "Irinotecan"
        ]
      },
      {
        "name": "Microsatellite Unstable (MSI-H)",
        "drugs": [
          "Pembrolizumab",
          "Nivolumab"
        ]
      }
    ]
  }
] as const;

export function findDisease(name: string): Disease | undefined {
  return DISEASES.find((d) => d.name === name);
}

export function subtypesFor(diseaseName: string): readonly DiseaseSubtype[] {
  return findDisease(diseaseName)?.subtypes ?? [];
}

export function drugsFor(diseaseName: string, subtypeName: string): readonly string[] {
  return subtypesFor(diseaseName).find((s) => s.name === subtypeName)?.drugs ?? [];
}
