"""Diagnostic bundle and plugin information in the original GSU screen style."""
from .i18n import for_api as _i18n_text
from pathlib import Path
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Screens.Screen import Screen
from twisted.internet.threads import deferToThread
from .warder_tools import run_task
from .warder_main import PLUGIN_NAME
from .release_history import load_notes

_SK={
    'Tools':'Nástroje',
    'About plugin':'O plugine',
    'Version':'Verzia',
    'Original project: Glass System Utility 13.20':'Pôvodný projekt: Glass System Utility 13.20',
    'Development and maintenance: Warder Evolution':'Vývoj a úpravy: Warder Evolution',
    'Thanks to the original Glass System Utility authors.':'Poďakovanie pôvodným autorom Glass System Utility.',
    'Receiver information, CAM/ECM management and diagnostics.':'Informácie o prijímači, správa CAM/ECM a diagnostika.',
    'Changes in this version':'Zmeny v tejto verzii',
    'Release notes are unavailable.':'Informácie o zmenách nie sú dostupné.',
    'Plugin version, authors and changes in the installed release.':'Verzia pluginu, autori a zmeny nainštalovaného vydania.',
    'Create diagnostic bundle':'Vytvoriť diagnostický balík',
    'Diagnostic bundle and plugin information.':'Diagnostický balík a informácie o plugine.',
    'Create one archive with system information and GSU logs.':'Vytvorenie jedného archívu s údajmi o systéme a logmi GSU.',
    'Creating diagnostic bundle…':'Vytváram diagnostický balík…',
    'Diagnostic collection failed.':'Zber diagnostiky sa nepodaril.',
    'Diagnostic bundle created:\n%s\n\nSize: %s KiB\n\nThe file is available on the receiver at the path above.':'Diagnostický balík bol vytvorený:\n%s\n\nVeľkosť: %s KiB\n\nSúbor nájdeš v prijímači na uvedenej ceste.',
    'Back':'Naspäť',
    'Unavailable':'Nedostupné',
}


def text(api,value):
    return _i18n_text(api,value,_SK)


def open_tools(session,api):session.open(ToolsScreen,api)


def about_text(api,root=None):
    root=Path(root) if root is not None else Path(__file__).parent
    def read_local(name,limit):
        try:
            with (root/name).open(encoding='utf-8',errors='replace') as stream:return stream.read(limit).strip()
        except OSError:return ''
    version=read_local('version',128) or text(api,'Unavailable')
    notes=read_local('release-notes.txt',16384).splitlines()
    changes='\n'.join(notes[1:]).strip() if notes and notes[0]=='GSU '+version else ''
    settings=api.get('config')
    language=getattr(getattr(getattr(settings,'osd',None),'language',None),'value','en')
    enabled=getattr(getattr(getattr(getattr(settings,'plugins',None),'GlassSysUtil',None),'par62',None),'value',True)
    changes=load_notes(root/'release-history.json',version,language if enabled else 'en') or changes
    return '\n'.join([PLUGIN_NAME,
        text(api,'Version')+': '+version,'',
        text(api,'Receiver information, CAM/ECM management and diagnostics.'),'',
        text(api,'Original project: Glass System Utility 13.20'),
        text(api,'Development and maintenance: Warder Evolution'),
        text(api,'Thanks to the original Glass System Utility authors.'),'',
        text(api,'Changes in this version'),changes or text(api,'Release notes are unavailable.'),'',
        'https://github.com/Evolution-by-Warder/GSU-Warder-Evolution'])


class ToolsScreen(Screen):
    def __init__(self,session,api):
        self.skin=api['ipkScript_center']
        Screen.__init__(self,session)
        self.api=api
        self.entries=[('bundle','Create diagnostic bundle','Create one archive with system information and GSU logs.')]
        self['list']=api['ListboxSys2']([])
        self['list'].onSelectionChanged.append(self.describe)
        self['descriptions']=Label('')
        self['red']=Label(text(api,'Back'));self['green']=Label(api['_']('Select'))
        self['actions']=ActionMap(['WizardActions','ColorActions'],{'ok':self.select,'green':self.select,'red':self.close,'back':self.close},-2)
        self.onLayoutFinish.append(self.prepare)

    def prepare(self):
        api=self.api;self.setTitle(text(api,'Tools'))
        rows=[]
        for kind,label,description in self.entries:
            rows.append([kind,api['MultiContentEntryText'](pos=(api['fhd'](25),0),size=(api['fhd'](535),api['fhd'](22)),font=0,text=text(api,label)),
                         api['MultiContentEntryPixmapAlphaTest'](pos=(0,api['fhd'](3)),size=(api['fhd'](15),api['fhd'](16)),png=api['LoadPixmap'](api['BP_ICO'] % 'green'))])
        self['list'].l.setList(rows);self.describe()

    def describe(self):
        row=self['list'].getCurrent()
        if row:
            entry=next((item for item in self.entries if item[0]==row[0]),None)
            self['descriptions'].setText(text(self.api,entry[2]) if entry else '')

    def select(self):
        row=self['list'].getCurrent()
        if not row:return
        if row[0]=='bundle':self.session.open(DiagnosticScreen,'bundle',self.api)


class DiagnosticScreen(Screen):
    def __init__(self,session,kind,api):
        if kind!='bundle':raise ValueError('Only diagnostic bundle creation is available here')
        self.skin=api['oscam_Files_scr2']
        Screen.__init__(self,session)
        self.kind,self.api=kind,api
        self.started,self.closed=False,False
        self['file_info']=ScrollLabel(text(api,'Creating diagnostic bundle…'))
        self['red']=Label(text(api,'Back'))
        self['actions']=ActionMap(['ColorActions','SetupActions','DirectionActions'],{'red':self.close,'cancel':self.close,'up':self['file_info'].pageUp,'down':self['file_info'].pageDown,'left':self['file_info'].pageUp,'right':self['file_info'].pageDown},-2)
        self.onLayoutFinish.append(self.start)
        self.onClose.append(self.cleanup)

    def start(self):
        if self.started or self.closed:return
        self.started=True
        self.setTitle(text(self.api,'Create diagnostic bundle'))
        self.request=deferToThread(run_task,self.kind)
        self.request.addCallback(self.done)
        self.request.addErrback(self.failed)

    def done(self,result):
        if self.closed:return
        value=text(self.api,'Diagnostic bundle created:\n%s\n\nSize: %s KiB\n\nThe file is available on the receiver at the path above.') % (result['path'],max(1,(result['bytes']+1023)//1024))
        self['file_info'].setText(value)

    def failed(self,failure):
        if not self.closed:self['file_info'].setText(text(self.api,'Diagnostic collection failed.'))
        return None

    def cleanup(self):self.closed=True


class AboutScreen(Screen):
    def __init__(self,session,api):
        self.skin=api['oscam_Files_scr2']
        Screen.__init__(self,session)
        self.api=api
        self['file_info']=ScrollLabel('')
        self['red']=Label(text(api,'Back'))
        self['actions']=ActionMap(['ColorActions','SetupActions','DirectionActions'],{'red':self.close,'cancel':self.close,'up':self['file_info'].pageUp,'down':self['file_info'].pageDown,'left':self['file_info'].pageUp,'right':self['file_info'].pageDown},-2)
        self.onLayoutFinish.append(self.prepare)

    def prepare(self):
        self.setTitle(text(self.api,'About plugin'))
        self['file_info'].setText(about_text(self.api))
