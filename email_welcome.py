from time import time
from util import elapsed
from util import safe_commit
import argparse

from models import emailer
from collections import defaultdict


emails_sent = """
peter.cumpson@ncl.ac.uk
tsp@ces.uc.pt
ukronman@kth.se
metwaly_eldakar@yahoo.com
simon.cobbold@hotmail.com
wtb1859@gmail.com
sshurtz@library.tamu.edu
muellerf.research@gmail.com
clari.gosling@open.ac.uk
jnfrdvsn@uw.edu
brommelstroet@gmail.com
guido.fanelli@unipr.it
m.van.selm@xs4all.nl
fintel@mit.edu
michael.thompson@complete-hv.com
me@prashanthvarma.com
tdietz@msu.edu
t.haastrup@kent.ac.uk
rturne15@uthsc.edu
showell3@nd.edu
bronwen.whitney@northumbria.ac.uk
ap113@cam.ac.uk
weixia@smu.edu.sg
stuart.a.lawson@gmail.com
jodi.a.schneider@gmail.com
wgsawyer@ufl.edu
lfurlong@imim.es
dr.mohammadhasan@gmail.com
arunkumar.962@rediffmail.com
edurne.zabaleta@gmail.com
david_osterbur@hms.harvard.edu
anlloyd@csu.edu.au
eng.franco@gmail.com
dinglei@sdu.edu.cn
vivoni@asu.edu
matthias.berth@gmail.com
aliciat@schoolph.umass.edu
cristina.tomas@uv.es
marchitelli@gmail.com
bcampb02@calpoly.edu
thoerns@gwdg.de
jacob.moorad
nicolas@limare.net
ruth.inigo@upc.edu
elarich@umich.edu
hinefuku@iastate.edu
armand.seguin@nrcan.gc.ca
ajith.abraham@ieee.org
raorben@gmail.com
erik.mullers@ki.se
jean-christophe.renauld@uclouvain.be
s.guerzoni@fondazioneimc.it
frodeman@unt.edu
jennielevineknies@gmail.com
koolaie@gmail.com
jmairal@gmail.com
hsinha@gmail.com
emma.yearwood@unimelb.edu.au
alira@sedici.unlp.edu.ar
laurie.wright@solent.ac.uk
w.sheate@imperial.ac.uk
i.lynch@bham.ac.uk
leonard.kemper@student.unisg.ch
costas.bouyioukos@issb.genopole.fr
angus.ferraro@googlemail.com
bunck@caltech.edu
scorullon@gmail.com
mhensle1@illinois.edu
romahane@indiana.edu
fite.abdelaziz.alrihawi@gmail.com
diriano@gmail.com
daniamann@gmail.com
pgkmohan@yahoo.com
ccloutie@ucalgary.ca
rec@secardiologia.es
carly.milliren@childrens.harvard.edu
caetanods1@gmail.com
bschmidt@sub.uni-goettingen.de
rajen.water@gmail.com
lynley.pound@gmail.com
m.patterson@elifesciences.org
klblock40@yahoo.com
yongweon.yi@gmail.com
juliacar@ceu.es
veeerendra@gmail.com
minohu@gmx.net
ppsimoes@gmail.com
memcvg@gmail.com
g.abt@hull.ac.uk
gokulkesavan@gmail.com
champa72@gmail.com
loveneet@dietkart.com
fergua@yahoo.ca
jackie.edwards@uts.edu.au
torressalinas@gmail.com
erinmaochu@gmail.com
fdebaste@ulb.ac.be
marschaefer@gmail.com
solbritt.andersson@lnu.se
jenny.c.dunn@gmail.com
mozfest2013a@hotmail.com
asa.matsuda@ieee.org
philip.machanick@gmail.com
omeally@gmail.com
nahid_lotfian@yahoo.com
mark@theaberdours.co.uk
jennie.burroughs@gmail.com
christine.chambers@dal.ca
bwolski@bond.edu.au
marta.lagom@udc.es
indla.pharmacology@gmail.com
ecsalomon@gmail.com
h.marshall@exeter.ac.uk
albertoclaro@albertoclaro.pro.br
aramirez@ramirezlab.net
dominika@work.swmed.edu
anders.lanzen@gmail.com
tomas.lagunas@udc.es
patrice.chalon@gmail.com
matt_andrews@hks.harvard.edu
grhyasen@gmail.com
c.inwood@griffith.edu.au
marc.deconchat@toulouse.inra.fr
jneubert@zbw.eu
vilhelmina.ullemar@ki.se
m
lanninj@missouri.edu
arunbiotechnologist@gmail.com
lkappos@uhbs.ch
vfridmacher@hotmail.com
ann.ewbank@asu.edu
lm.ogorman@qut.edu.au
erinrobinson@esipfed.org
b.drinkwater@bristol.ac.uk
verrico@bcm.edu
charlotte.brown@gmail.com
ketterso@indiana.edu
thwillia@gmail.com
kallarahul@gmail.com
kavubob@gmail.com
exergamelab@gmail.com
imre.vida@charite.de
buckleyy@tcd.ie
juan@uniovi.es
djrozell@gmail.com
monirehgharibeniazi@yahoo.com
oliver.jones@rmit.edu.au
kenny048@umn.edu
erik.stattin@gmail.com
sglegg@cw.bc.ca
ohalloranc@ecu.edu
zmj@zmjones.com
daniysusbromas@yahoo.ees
danbrowne@gmail.com
sgantayat67@rediffmail.com
jacob.leachman@wsu.edu
iftachn@post.tau.ac.il
r.fagan@sheffield.ac.uk
dagmara.chojecki@ualberta.ca
geraldine.laloux@yale.edu
still.pestill@gmail.com
rolando.milian@yale.edu
mail_me_on_line@yahoo.com
deloubens@irphe.univ-mrs.fr
dirk.haehnel@phys.uni-goettingen.de
chayanikabarman123@gmail.com
oroszgy@gmail.com
anahi.balbi@frontiersin.org
ea866311@ohio.edu
marco.tullney@fu-berlin.de
dkolah@rice.edu
g.louppe@gmail.com
pfafard@uottawa.ca
veronica.salido@um.es
wolass@gmail.com
apai@spelman.edu
dalloliogm
admin@fisica.udea.edu.co
andre.goergens@uk-essen.de
vblago@gmail.com
richarow@usc.edu
joaoantonio@yahoo.com
pultz@ku.edu
kaltrina.nuredini@yahoo.com
sandraklatt@gmx.net
stefan.Mueller@fu-berlin.de
noha@cybrarians.info
kristoffer.l.karlsson@chalmers.se
turner@usf.edu
jordipapsgmail.com
mikeknee@gmail.com
paola.villani@polimi.it
rociomorcillo@gmail.com
ganley@psy.fsu.edu
klaas.vandepoele@gmail.com
grosd@musc.edu
negaresma@gmail.com
ab@ab.com
christina.godfrey@articuatescience.com
lewis.mitchell@adelaide.edu.au
emily.alvino@qut.edu.au
boes@pitt.edu
gustavosmotta@gmail.com
amy_brand@harvard.edu
f.murphy@latrobe.edu.au
m.p.morgenstern@gmail.com
paulatraver@gmail.com
tomofumi.okuda@jp.sony.com
hankin@ufl.edu
sadegh.hatamkhani@yahoo.con
peter.doorn@dans.knaw.nl
biserkov@gmail.com
lisa.lodwick@googlemail.com
da.frost@qut.edu.au
josekarvalho@gmail.com
gbb@ipac.caltech.edu
a.gaskett@auckland.ac.nz
uchikawa214@gmail.com
takeoutweight@hotmail.com
mal.ross@nonlinear.com
gfr.abdul@yahoo.co.in
c.oyler@orcid.org
contact@jfstich.com
piotrsmolnicki@gmail.com
shenmeng@live.unc.edu
acabrera@universidadecotec.edu.ec
ahchen@ua.edu
gabriel.wallau@gmail.com
dfreelon@gmail.com
ca.mclean@auckland.ac.nz
shelleyminteer@gmail.com
aizenman@cox.net
patternizer@gmail.com
s.hu@awmc.uq.edu.au
iremaseda@gmail.com
andree@uri.edu
joan.moranta@ba.ieo.es
luisdiazdelrio@hotmail.com
cb1914a@student.american.edu
awasom.afuh@ttu.edu
cpachecoiii@gmail.com
jpo@ebi.ac.uk
ashikasjayanthy@gmail.com
qaziuzaina@gmail.com
andrea.burattin@gmail.com
bussonniermatthias@gmail.com
a.alabdali@warwick.ac.uk
erich.brenner@i-med.ac.at
evelien.vandeperre@ugent.be
marialisa.scata@gmail.com
kelleydwhitten@gmail.com
garnier@wehi.edu.au
kganeshp@gmail.com
carlcold.cc@gmail.com
dr.jahuja@gmail.com
challa.anilkumar@gmail.com
marc.robinsonrechavi@gmail.com
rnpcp942@yahoo.co.jp
maria.jenmalm@me.com
jenserikmai@gmail.com
mathijs_van_leeuwen@hotmail.com
rmcw@st-andrews.ac.uk
donovan.maryk@gmail.com
kate.weatherall@meditechmedia.com
fernan@iib.unsam.edu.ar
kevin.drees@okstate.edu
artemij.keidan@uniroma1.it
bjshops@yahoo.com
violeta_gh@usal.es
cmarsh12@gmail.com
christopher.hodge@visioneyeinstitute.com.au
contato@skrol.com
rhilliker@columbia.edu
administrator@palaeontologyonline.com
will.whiteley@gmail.com
ejimenez@gmail.com
consort@ohri.ca
breiter@usf.edu
caterina.viglianisi@unifi.it
analauda@gmail.com
mikhail.spivakov@babraham.ac.uk
elizabeth.kingdom@gmail.com
matt.hall@unibas.ch
julia@turningforward.org
mforeman@msm.edu
dfboehni@utmb.edu
delgado@gmail.com
briganti@ifo.it
gianluca@dellavedova.org
andrew2153@gmail.com
simon@simula.no
weaverj@unimelb.edu.au
alimulyohadidr@gmail.com
kevin.mansfield@ucl.ac.uk
mark.skilton@wbs.ac.uk
iveta.simera@csm.ox.ac.uk
svetal.shukla@nirmauni.ac.in
a.dempsey@murdoch.edu.au
murdiea@missouri.edu
moussa.benhamed@u-psud.fr
maxima.bolanos@uv.es
nicholas.badcock@mq.edu.au
isyelueze@gmail.com
dhocking@unh.edu
schacht@geneseo.edu
nkannankutty@yahoo.com
lskalla@michaeldbaker.com
cwilhite@salud.unm.edu
hct194@gmail.com
susanleemburg@gmail.com
amanda.cooper@queensu.ca
mardomidepaz@gmail.com
jake@jakebowers.org
am187k@nih.gov
eschenk@usgs.gov
hlapp+impst1@drycafe.net
melanie.bertrand@asu.edu
bgagee@vt.edu
kelly.elizabeth.miller@gmail.com
leonardo.trasande@nyumc.org
carola.tilgmann@med.lu.se
dargan@atmos.washington.edu
kirby.shannon@gmail.com
nick.gardner@gmail.com
blwetze@terpmail.umd.edu
manusfonseca@gmail.com
mahbubadilruba@gmail.com
alexander.pisarchik@ctb.upm.es
paul.thirion@ulg.ac.be
ajw51@le.ac.uk
jim.witschey@gmail.com
daniel_von_schiller@hotmail.com
margarida.rego@fd.unl.pt
manuel.durand-barthez@enc.sorbonne.fr
jimbowen1979@gmail.com
leonderczynski@gmail.com
nicholasjameshudson@yahoo.com
dave.number8@gmail.com
m.calver@murdoch.edu.au
harriet.barker@surrey.ac.uk
phil.levin@netzero.net
gemma.masdeu@ub.edu
kkoray87@gmail.com
salhandivya@gmail.com
titus@idyll.org
nglazer@fas.harvard.edu
billy.meinke@gmail.com
mmichalak@gmail.com
pittmixer@gmail.com
kamakshi.rajagopal@gmail.com
dritoshi@gmail.com
ramsyagha@gmail.com
mrtz.milani@gmail.com
susanne.manz@luks.ch
jacqueline.arciniega@nyumc.org
m-allkhamis@hotmail.com
lorna.peterson2401@gmail.com
joe.mirza@uclh.nhs.uk
ggruere@gmail.com
e.largy@gmail.com
shibbyin@gmail.com
rosieusedv@gmail.com
barwil@gmail.com
nikdholakia@gmail.com
ddecarv@uhnresearch.ca
vegapchirinos@gmail.com
danielrandles@gmail.com
matt.holland@nwas.nhs.uk
ikeuchi.ui@gmail.com
ssiyahhan@gmail.com
gupta59@illinois.edu
simon.elliott@tyndall.ie
alicia.franco@udc.es
terinthanas@gmail.com
t.espinosa.s@gmail.com
omidalighasem49@gmail.com
prateek.mahalwar@tuebingen.mpg.de
marc.neumann@bc3research.org
jburkhardt@uri.edu
tmartins@bcs.uc.pt
adela.feldru@gmail.com
mikko.ojanen@helsinki.fi
berridge@umich.edu
jbhogen@yahoo.com
jennifer_costanza@ncsu.edu
yildiraykeskin@yahoo.com
dan.lawson@bristol.ac.uk
axfelix@gmail.com
1920wr@gmail.com
amparocosta71@gmail.com
toshifum@ualberta.ca
thhaverk@gmail.com
mrassafiani@gmail.com
keith.collier@rubriq.com
ghre
miika.tapio@gmail.com
digitalbio@gmail.com
phillip.white@duke.edu
soiland-reyes@cs.manchester.ac.uk
beatrice.marselli@epfl.ch
simon.sherry@dal.ca
cyc3700@gmail.com
m.salamattalab@gmail.com
tricia.mccabe@sydney.edu.au
matthewomeagher@gmail.com
bsul@nih.gov
baeza.antonio@gmail.com
chris.carswell@springer.com
rhonda.allard.ctr@usuhs.edu
samantha.stehbens@gmail.com
ahmedbassi@gmail.com
deveshkumarjoshi@gmail.com
a.n.scott@ids.ac.uk
mihai.podgoreanu@duke.edu
lemosbioinfo@gmail.com
sanzce@gmail.com
muliasulistiyono@hotmail.com
jeramia.ory@gmail.com
patshine@gmail.com
steve.p.lee@gmail.com
anders.wandahl@ki.se
walter.finsinger@univ-montp2.fr
cynthia.parr@ars.usda.gov
test23@e.com
cawein@live.unc.edu
scgooch@uwaterloo.ca
ngomez@udc.es
nicoleca@stanford.edu
altmetrics.ifado@gmx.de
pbeile@mail.ucf.edu
contact@ryanlfoster.com
juanmaldonado.ortiz@gmail.com
david.w.carter@noaa.gov
a.algra@umcutrecht.nl
raymond.white@uwa.edu.au
makman@ucdavis.edu
nethmin999@gmail.com
barbara.prainsack@gmail.com
linder.bastian@googlemail.com
dgrapov@gmail.com
ucfagls@gmail.com
foster@uchicago.edu
barbro.hellquist@onkologi.umu.se
colditzjb@gmail.com
shoaibsufi@gmail.com
amdrauch@ucdavis.edu
pkiprof@d.umn.edu
iserra73@gmail.com
manubue@yahoo.es
kljensen@alaska.edu
t.gruber@lboro.ac.uk
cesareni@uniroma2.it
claire-stewart@northwestern.edu
sportart@gmail.com
f.correia.profissional@gmail.com
andy@mydocumate.com
mjvs8822@gmail.com
quackenbushs@missouri.edu
sanand@nichq.org
bouche.fred@gmail.com
pierre-michel.forget@mnhn.fr
freaner@unam.mx
i.munfer@gmeil.com
ciaran.quinn@nuim.ie
jan.havlicek@ruk.cuni.cz
julia_sollenberger@urmc.rochester.edu
mokhtari21@hotmail.com
fatima.raja@ucl.ac.uk
gormleya@landcareresearch.co.nz
rosarie.coughlan@queensu.ca
psm_bu@india.com
farhadshokraneh@gmail.com
hsenior@aracnet.com
drsaraserag@aucegypt.edu
sally.a.keith@gmail.com
b.hall@bangor.ac.uk
mbjones.89@gmail.com
pierrich.plusquellec@umontreal.ca
mzs227@gmail.com
nakul777@gmail.com
quinn.jamiem@gmail.com
rafael.calsaverini@gmail.com
ccbenner@ucdavis.edu
kbranch@uri.edu
sandra_destradi@yahoo.de
kdough03@gmail.com
a.scott@ids.ac.uk
ir46@le.ac.uk
l.kenny@ioe.ac.uk
jsoutter@uwindsor.ca
michaela.saisana@jrc.ec.europa.eu
canthony@jcu.edu
djacobs@rider.edu
kat.bussey@gmail.com
kumbharrajendra@yahoo.co.in
lmtd@sun.ac.za
b.yousefi@tum.de
adamt@uow.edu.au
kate.parr@liverpool.ac.uk
alfonso.infante@uhu.es
d.dunlap@neu.edu
xosearegos@gmail.com
dwanecateslaw@yahoo.com
sadaf.ashfaque@gmail.com
fjmanza@ugr.es
david.kalfert@email.cz
matthew.parker@uky.edu
pjbh1@stir.ac.uk
totalimpact@jcachat.com
meri.raggi@unibo.it
mickic20@yahoo.com
markel.vigo@manchester.ac.uk
rdaniel@ohri.ca
m.boyle@griffith.edu.au
jessica.breiman@gmail.com
asa.langefors@biol.lu.se
jsmith@sympatico.ca
kzborzynska@gmail.com
mark.farrar@manchester.ac.uk
alebisson@gmail.com
ekarakaya@gmail.com
eguacimara@gmail.com
bgoodridge@bren.ucsb.edu
bruno.bellisario@gmail.com
amir.sariaslan@psych.ox.ac.uk
stacy.konkiel+nachos@gmail.com
cchan3330@gmail.com
ulrich.schroeders@uni-bamberg.de
j.bosman@uu.nl
dtpalmer@hku.hk
majkaweber@aol.de
n03er953@gmail.com
j.kazbekov@cgiar.org
trevor.johnowens@gmail.com
dieter.lukas@gmail.com
spergam@fhcrc.org
mitchell.thompson@berkeley.edu
erlingj@rki.de
stacy.konkiel+buttons@gmail.com
hcrogman@yahoo.com
mdfrade@gmail.com
jjotto@rutgers.edu
goldman@med.unc.edu
leonardo.candela@isti.cnr.it
twheatland@assumption.edu
gilles.frison@polytechnique.edu
kn11284@seeu.edu.mk
pontika.nancy@gmail.com
jon.hill@imperial.ac.uk
trujillo.valentina@gmail.com
a.teacher@exeter.ac.uk
barry@barold.com
david.bailey@glasgow.ac.uk
onkenj@mail.nih.gov
abreiter@informatik.uni-bremen.de
regan.early@gmail.com
sadaf.ashfaque@yahoo.com
davidwright37@aol.com
marc.c-scott@vu.edu.au
kaveh@bazargan.org
gianluigi.filippelli@gmail.com
h.talebiyan@gmail.com
degoss@gmail.com
r.a.higman@reading.ac.uk
bruno.danis@ulb.ac.be
aakella@aip.org
ekuru@indiana.edu
loet@leydesdorff.net
rachel.nowak@monash.edu
fatemeh.nadimi5@gmail.com
sumanta.patro@yahoo.com
naoto.kojima@gmail.com
thabash@apa.org
adam.byron@gmail.com
r.bryant@orcid.org
apanigab@gmail.com
annelewis40th@gmail.com
rams.aguilar@gmail.com
bct3@psu.edu
assafzar@gmail.com
david.ross@sagepub.co.uk
danielclark@bpp.com
ericaburl@gmail.com
cng_kng@yahoo.com
eirik.sovik@gmail.com
mpace01s@illinois.edu
bflammang@post.harvard.edu
gattuso2@obs-vlfr.fr
john.parker@asu.edu
egil@du.edu
rchampieux@gmail.com
johannes.hoja@gmail.com
aalfonso@unav.es
mmalves@fe.up.pt
gigi@biocomp.unibo.it
nicola.misani@unibocconi.it
waterhlz@gmail.com
andrew.treloar@gmail.com
nathaliasavila@gmail.com
jens.malmkvist@anis.au.dk
afbailey@vt.edu
nardello@unica.it
tkind@ucdavis.edu
maren@tamu.edu
adavis-alteri@albany.edu
tjacobson@albany.edu
peter.bower@manchester.ac.uk
samuel.bolton77@mail.com
dr.jonte@gmail.com
siouxsie.wiles@gmail.com
villa@lcc.uma.es
wkeithcampbell@gmail.com
g.lozano@csic.es
katinatoufexis@hotmail.com
keith@uri.edu
gatien.lokossou@gmail.com
d.mcelroy@uel.ac.uk
herrie.schalekamp@uct.ac.za
gss1@cornell.edu
prabhakar.marepalli@gmail.com
tritemio@gmail.com
mirdelpal@gmail.com
martin.kamler@gmail.com
barbara@bbneves.com
sjones@sc.edu
mdriscoll@library.ucsb.edu
pennyb@gmail.com
karen.vella@qut.edu.au
paul.frankland@gmail.com
barchas@austin.utexas.edu
j.beggs@auckland.ac.nz
bgallagher@mail.uri.edu
paul.maharg@anu.edu.au
renytyson@hotmail.com
wangfeng.w@gmail.com
krother@academis.eu
cgcamero@gmail.com
paolo.righi@unibo.it
schang72@umd.edu
lherzberg@ku.edu
gary.motteram@manchester.ac.uk
mullain@fas.harvard.edu
karen.gutzman@northwestern.edu
michelle.carnegie@gmail.com
dzwinel@agh.edu.pl
torsten.seemann@gmail.com
renata.freitas@ibmc.up.pt
amir.aryani@gmail.com
rmasmuss@gmail.com
warrenkoch@gmail.com
mpop@umd.edu
ykondo@kumamoto-u.ac.jp
lettner.chr@gmail.com
fmylonas@image.ntua.gr
p.loria@uws.edu.au
juliema@illinois.edu
krantisinha@rediffmail.com
sandy.campbell@ualberta.ca
robert_campbell@cbu.ca
ashley.cnchen@gmail.com
gandipalem@gmail.com
idf2@cornell.edu
phillip.melton@uwa.edu.au
akinlo@gmail.com
rogersm@pitt.edu
lalba@flog.uned.es
manuelbehmel@gmail.com
p.crook@latrobe.edu.au
girish-bathla@uiowa.edu
ssampson@sun.ac.za
curttalkthai@gmail.com
florian.duclot@med.fsu.edu
manuela.degregori@unipv.it
h.webb
brookss1@kgh.kari.net
science@vort.org
sa.kornilov@gmail.com
machtmes@ohio.edu
erin.braswell@gmail.com
siul.shl@gmail.com
mlitton@utk.edu
h2izadi@uwaterloo.ca
jshepard@library.berkeley.edu
meihalt@gmail.com
phaedra@surgery.org
pnvaughn@uh.edu
wilcoxcl@hawaii.edu
ridavide@gmail.com
vanesa.loureiro@gmail.com
deborah.fitchett@gmail.com
bleveck@ucmerced.edu
gerben@gerbenzaagsma.org
bette.rathe@unco.edu
kelly.bogh@nrcresearchpress.com
amogh.ambardekar@gmail.com
liefeld@broadinstitute.org
julia.leong@rmit.edu.au
dgilton@mail.uri.edu
belazzbelazz@gmail.com
demariasn@mail.nih.gov
tarja.kokkola@uef.fi
claire.cobley@gmail.com
mehdi.golari@gmail.com
elizabeth.farrell@yahoo.com
thomas.kastner@aau.at
j.ewart@griffith.edu.au
john.cronin@eui.eu
mdgroover@bsu.edu
carawong@illinois.edu
wjavac@hotmail.com
william.gunn@mendeley.com
sophiebuigues@gmail.com
shop@brianmcgill.org
jmoses@primaryresearch.com
nicstah@hotmail.com
C.Rowan@warwick.ac.uk
david.michels@dal.ca
apding@gmail.com
julian.garcia@pobox.com
westonplatter@gmail.com
a.nuriddinov94@gmail.com
abeisler@unr.edu
vtsiligiris@gmail.com
jennifer.fishman@mcgill.ca
cristina.blancoandujar.09@ucl.ac.uk
mattecologist@gmail.com
angelica.risquez@ul.ie
david.gatfield@unil.ch
sfm@mail.nih.gov
beaufrer@uoguelph.ca
dkbaldr@gmail.com
angelamaria.rizzo@unimi.it
tom.finger@ucdenver.edu""".split()


def email_everyone(filename):

    with open(filename, "r") as f:
        lines = f.read().split("\n")
        print "found {} lines".format(len(lines))

    total_start = time()
    row_num = 0
    people_to_email = defaultdict(dict)

    # skip header row
    for line in lines[1:]:
        row_num += 1

        try:
            (url_slug,orcid_id,twitter_id,email,stripe_id,is_advisor,given_name,surname,created,last_viewed_profile) = line.split(",")

            is_subscribed = len(stripe_id)>0 or is_advisor=="t"

            people_to_email[email] = {
                "orcid_id": orcid_id,
                "is_subscribed": is_subscribed,
                "given_name": given_name,
                "surname": surname,
                "refunded": False
            }
            print u"added person {} {} {}".format(row_num, email, people_to_email[email])
        except ValueError:
            print u"couldn't parse", line

    with open("data/impactstory_refunds.csv", "r") as f:
        lines = f.read().split("\r")
        print "found {} lines".format(len(lines))

    for line in lines[1:]:
        try:
            (stripe_created,full_name,email) = line.split(",")
            if email in people_to_email:
                people_to_email[email]["refunded"] = True
                print "added refunded true to dict for", email
            else:
                people_to_email[email] = {
                    "orcid_id": None,
                    "is_subscribed": False,
                    "refunded": False
                }
                print "added new emailee true to dict for", email
        except ValueError:
            print "couldn't parse"

    # email = "heather@impactstory.org"
    # send_tng_email("heather@impactstory.org", people_to_email[email])

    num_sending = 0
    num_not_sending = 0
    for email, addressee_dict in people_to_email.iteritems():
        if addressee_dict["is_subscribed"] or addressee_dict["refunded"]:
            if email in emails_sent:
                num_not_sending += 1
                print "not sending email to", email, "because already sent"
            else:
                print "WOULD send email to", email
                num_sending += 1
                send_tng_email(email, addressee_dict)
    print "num_not_sending", num_not_sending
    print "num_sending", num_sending

def send_tng_email(email, addressee_dict, now=None):

    # if os.getenv("ENVIRONMENT", "testing") == "production":
    #     email = profile.email
    # else:
    #     email = "heather@impactstory.org"

    report_dict = {"profile": addressee_dict}

    #### KEEEP THIS HERE FOR NOW, so that don't spam other people
    # email = 'hpiwowar@gmail.com'

    msg = emailer.send(email, "The new Impactstory: Better. Freer.", "welcome", report_dict)

    print "SENT EMAIL to ", email





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('filename', type=str, help="filename to import")
    parsed = parser.parse_args()

    start = time()
    email_everyone(parsed.filename)
    print "finished update in {}sec".format(elapsed(start))


