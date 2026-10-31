#!/usr/bin/env python3
"""Stage a new repair IPK without advancing any published update manifest."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='13.40-r95'


def main():
    paths=[ROOT/'update/candidate.json',ROOT/'update/stable.json',ROOT.parent/'restoration/update/candidate.json']
    before={str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    current=ROOT/'src/GlassSysUtil/version'
    assert current.read_text().strip() in ('13.40-r94',VERSION)
    current.write_text(VERSION+'\n')
    (ROOT/'update/RELEASE-NOTES.md').write_text('GSU '+VERSION+'\n\nSpoľahlivejší prechod zo starej verzie a overenie dokončenej inštalácie.\nPrehľadná, preložená história posledných štyroch vydaní.\n')
    document=json.loads((ROOT/'update/RELEASE-NOTES.i18n.json').read_text())
    notes=dict(zip(('sk','cs','en','de','pl','hu','ru','fr','it','es'),(
        'Spoľahlivejšia inštalácia a prechod zo staršej verzie.',
        'Spolehlivější instalace a přechod ze starší verze.',
        'More reliable installation and upgrades from older versions.',
        'Zuverlässigere Installation und Aktualisierung älterer Versionen.',
        'Pewniejsza instalacja i aktualizacja starszych wersji.',
        'Megbízhatóbb telepítés és frissítés a régebbi verziókról.',
        'Надёжнее установка и обновление старых версий.',
        'Installation et mise à jour des anciennes versions plus fiables.',
        'Installazione e aggiornamento delle vecchie versioni più affidabili.',
        'Instalación y actualización de versiones anteriores más fiables.')))
    if document['version']!=VERSION:
        document['entries'].insert(0,{'version':VERSION,'date':'31.10.2026','notes':notes})
    document.update(version=VERSION,notes=notes)
    (ROOT/'update/RELEASE-NOTES.i18n.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    assert before=={str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    out=ROOT/'build';out.mkdir(exist_ok=True)
    (out/'feed-isolation.json').write_text(json.dumps(before,indent=2)+'\n')
    print('Prepared '+VERSION+'; all published update manifests unchanged')


if __name__=='__main__':main()
