# -*- coding: utf-8 -*-

from django.contrib.gis.db import models
from django.utils.safestring import mark_safe
from django.core.cache import cache


class Status(models.Model):
    "stavy zobrazeni konkretniho objektu, vrstvy apod. - aktivni, navrzeny, zruseny, ..."
    nazev   = models.CharField(unique=True, max_length=255)         # Nazev statutu
    desc    = models.TextField(null=True, blank=True)               # Description
    show    = models.BooleanField()                                 # Zobrazit uzivateli zvenci
    show_TU = models.BooleanField()                                 # Zobrazit editorovi mapy

    class Meta:
        verbose_name_plural = "statuty"
    def __unicode__(self):
        return self.nazev

class Vrstva(models.Model):
    "vrstvy, ktere se zobrazi v konkretni mape"
    nazev   = models.CharField(max_length=255)                      # Name of the layer
    slug    = models.SlugField(unique=True, verbose_name=u"Název v URL")  # Vrstva v URL
    desc    = models.TextField(null=True, blank=True)               # Description
    status  = models.ForeignKey(Status)              # zobrazovaci status
    order   = models.PositiveIntegerField()
    remark  = models.TextField(null=True, blank=True) # Interni informace o objektu, ktere se nebudou zobrazovat!

    class Meta:
        verbose_name_plural = "vrstvy"
        ordering = ['order']
    def __unicode__(self):
        return self.nazev

    
class Znacka(models.Model):
    "mapove znacky vcetne definice zobrazeni"
    nazev   = models.CharField(unique=True, max_length=255)   # Name of the mark
    slug    = models.SlugField(unique=True, verbose_name=u"název v URL")  # Vrstva v URL
    
    # Relationships
    vrstva  = models.ForeignKey(Vrstva)              # Kazda znacka lezi prave v jedne vrstve
    status  = models.ForeignKey(Status)              # kvuli vypinani
    
    # content 
    desc    = models.TextField(null=True, blank=True) # podrobny popis znacky
    remark  = models.TextField(null=True, blank=True) # Interni informace o objektu, ktere se nebudou zobrazovat!
    
    # Base icon and zoom dependent display range
    default_icon = models.ImageField(null=True, upload_to='ikony') # XXX: zrusit null=True
    minzoom = models.PositiveIntegerField(default=1)
    maxzoom = models.PositiveIntegerField(default=10)

    url     = models.URLField(null=True, blank=True, help_text=u"ukáže se u všech míst s touto značkou, pokud nemají vlastní url")
    
    class Meta:
        verbose_name_plural = "značky"
    def __unicode__(self):
        return self.nazev

class ViditelneManager(models.GeoManager):
    "Pomocny manazer pro dotazy na Poi se zobrazitelnym statuem"
    def get_query_set(self):
        return super(ViditelneManager, self).get_query_set().filter(status__show=True, znacka__status__show=True)

class Poi(models.Model):
    "Misto - bod v mape"
    nazev   = models.CharField(max_length=255, blank=True)   # Name of the location
    
    # Relationships
    znacka  = models.ForeignKey(Znacka)          # "Znacky"   - misto ma prave jednu
    status  = models.ForeignKey(Status)          # "Statuty"  - misto ma prave jeden
    
    # "dulezitost" - modifikator minimalniho zoomu, ve kterem se misto zobrazuje. 
    # Cim vetsi, tim vice bude poi videt, +20 = bude videt vydycky
    # Cil je mit vyber zakladnich objektu viditelnych ve velkych meritcich
    # a zabranit pretizeni mapy znackami v prehledce.
    # Lze pouzit pro placenou reklamu! ("Vas podnik bude videt hned po otevreni mapy")
    dulezitost = models.SmallIntegerField(default=0)
    
    # Geographical intepretation
    geom    = models.PointField(verbose_name=u"Poloha",srid=4326)
    objects = models.GeoManager()
    
    # Own content (facultative)
    desc    = models.TextField(null=True, blank=True)
    desc_extra = models.TextField(null=True, blank=True, help_text="text do podrobnějšího výpisu podniku (mimo popup)")
    url     = models.URLField(null=True, blank=True)  # Odkaz z vypisu - stranka podniku apod.
    # address = models.CharField(max_length=255, null=True, blank=True)
    remark  = models.TextField(null=True, blank=True) # Interni informace o objektu, ktere se nebudou zobrazovat!

    # navzdory nazvu jde o fotku v plnem rozliseni
    foto_thumb  = models.ImageField(null=True, blank=True, upload_to='foto')
    
    viditelne = ViditelneManager()
    
    class Meta:
        verbose_name_plural = "místa"
    def __unicode__(self):
        if self.nazev:
            return self.nazev
        return unicode(self.znacka)
    def get_absolute_url(self):
        return "/misto/%i/" % self.id

from django.db.models.signals import post_save
def invalidate_cache(sender, instance, **kwargs):
    if sender in [Status, Vrstva, Znacka, Poi]:
        cache.clear()
post_save.connect(invalidate_cache)
    

UPRESNENI_CHOICE = (
        ('novy', u'Nový'),
        ('reseno', u'V řešení'),
        ('vyreseno', u'Vyřešeno'),
        ('zamitnuto', u'Zamítnuto'),
)

class Upresneni(models.Model):
    """
    Tabulka pro uzivatelske doplnovani informaci do mapy. 

    Prozatim na proncipu rucniho prepisu udaju v adminu.
    Vyzchazi z POI, ale nekopiruje se do ni.
    Slouzi predevsim k doplneni informace k mistu. Nektera pole mohou byt proto nefunkncni.
    Pouziva se pouze v Zelene mape, v PNK zatim neaktivni
    """

    misto  = models.ForeignKey(Poi, blank=True, null=True) # Odkaz na objekt, ktery chce opravit, muze byt prazdne.
    email  = models.EmailField(verbose_name=u"Váš e-mail (pro další komunikaci)", null=True)    # Prispevatel musi vyplnit email.
    status  = models.CharField(max_length=10,choices=UPRESNENI_CHOICE) 
    desc    = models.TextField(verbose_name=u"Popis (doplnění nebo oprava nebo popis nového místa, povinné pole)",null=True)
    url     = models.URLField(verbose_name=u"Odkaz, webové stránky místa (volitelné pole)",null=True, blank=True)  # Odkaz z vypisu - stranka podniku apod.
    address = models.CharField(verbose_name=u"Adresa místa, popis lokace (volitelné pole)",max_length=255, null=True, blank=True)

    class Meta:
        verbose_name_plural = u"upřesnění"
    def __unicode__(self):
        return u"%s - %s" % (self.misto, self.email)
    
class Staticpage(models.Model):
    """
    Tabulka statickeho obsahu webu, jednoduchy CMS

    Pouziva se pouze v Zelene mape, v PNK zatim neaktivni
    """

    slug    = models.SlugField(unique=True, verbose_name="Slug")  # extenze v URL
    head    = models.TextField(verbose_name=u"Header section (additional css, js, etc.)",null=True, blank=True)
    title   = models.CharField(verbose_name=u"Titulek straky",max_length=255, null=True, blank=True)
    short   = models.TextField(verbose_name=u"Zkraceny html obsah (nahled)",null=True)
    content = models.TextField(verbose_name=u"Html obsah",null=True)
    
    def __unicode__(self):
        return self.title
