import unittest
from nose.tools import nottest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
import requests
from ddt import ddt, data
import requests_cache

import publication

requests_cache.install_cache('oadoa_requests_cache', expire_after=60*60*24*7)  # expire_after is in seconds

test_dois = [
    # open from juan
    ("10.1002/cncr.30235", "http://doi.org/10.1002/cncr.30235", "cc-by"),
    ("10.1007/s00117-016-0151-5", "http://link.springer.com/content/pdf/10.1007%2Fs00117-016-0151-5.pdf", "unknown"),
    ("10.1016/s0140-6736(15)01087-9", "http://doi.org/10.1016/s0140-6736(15)01087-9", "cc-by"),
    ("10.1016/s0140-6736(16)30825-x", "http://doi.org/10.1016/s0140-6736(16)30825-x", "cc-by"),
    ("10.1038/mt.2016.119", "http://www.nature.com/mt/journal/v24/n10/pdf/mt2016119a.pdf", "cc-by"),
    ("10.1038/nature.2016.20302", "http://www.nature.com:80/polopoly_fs/1.20302!/menu/main/topColumns/topLeftColumn/pdf/nature.2016.20302.pdf", "unknown"),
    ("10.1038/nutd.2016.20", "http://doi.org/10.1038/nutd.2016.20", "cc-by"),
    ("10.1038/srep29901", "http://doi.org/10.1038/srep29901", "cc-by"),
    ("10.1056/nejmoa1516192", "http://www.nejm.org/doi/pdf/10.1056/NEJMoa1516192", "unknown"),
    ("10.1056/nejmoa1606220", "http://www.nejm.org/doi/pdf/10.1056/NEJMoa1606220", "unknown"),
    # ("10.1136/bmj.i1209", "http://www.bmj.com/content/bmj/352/bmj.i1209.full.pdf", "cc-by-nc"), #keeps changing whether has static in url or not
    ("10.1136/bmj.i2716", "http://www.bmj.com/content/bmj/353/bmj.i2716.full.pdf", "cc-by"),
    ("10.1186/s12885-016-2505-9", "http://doi.org/10.1186/s12885-016-2505-9", "cc-by"),
    ("10.1186/s12995-016-0127-4", "http://doi.org/10.1186/s12995-016-0127-4", "cc-by"),
    ("10.1371/journal.pone.0153011", "http://doi.org/10.1371/journal.pone.0153011", "cc-by"),
    ("10.17061/phrp2641646", "http://doi.org/10.17061/phrp2641646", "cc-by-nc-sa"),
    ("10.18632/oncotarget.10653", "http://www.impactjournals.com/oncotarget/index.php?journal=oncotarget&page=article&op=download&path%5B%5D=10653&path%5B%5D=33731", "cc-by"),
    ("10.2147/jpr.s97759", "http://doi.org/10.2147/jpr.s97759", "cc-by-nc"),
    ("10.3322/caac.21332", "http://onlinelibrary.wiley.com/doi/10.3322/caac.21332/pdf", "unknown"),
    ("10.3322/caac.21338", "http://onlinelibrary.wiley.com/doi/10.3322/caac.21338/pdf", "unknown"),
    ("10.4103/1817-1737.185755", "http://doi.org/10.4103/1817-1737.185755", "cc-by-nc-sa"),

    # closed from juan
    ("10.1002/pon.4156", None, "unknown"),
    ("10.1016/j.cmet.2016.04.004", None, "unknown"),
    ("10.1016/j.urolonc.2016.07.016", None, "unknown"),
    ("10.1016/s0140-6736(16)30383-x", None, "unknown"),
    ("10.1016/s2213-2600(15)00521-4", None, "unknown"),
    ("10.1038/nature18300", None, "unknown"),
    ("10.1038/ncb3399", None, "unknown"),
    ("10.1056/nejmoa1600249", None, "unknown"),
    ("10.1056/nejmoa1603144", None, "unknown"),
    ("10.1080/03007995.2016.1198312", None, "unknown"),
    ("10.1093/annonc/mdw322", None, "unknown"),
    ("10.1093/jnci/djw035", None, "unknown"),
    ("10.1093/pm/pnw115", None, "unknown"),
    ("10.1111/add.13477", None, "unknown"),
    ("10.1126/science.aad2149", None, "unknown"),
    ("10.1126/science.aaf1490", None, "unknown"),
    ("10.1136/bmj.i788", None, "unknown"),
    ("10.1136/thoraxjnl-2016-208967", None, "unknown"),
    ("10.1148/radiol.2016151419", None, "unknown"),
    ("10.1158/1055-9965.epi-15-0924", None, "unknown"),
    ("10.1177/0272989x15626384", None, "unknown"),

    # more examples that were broken at some point
    ("10.6084/m9.figshare.94318", "http://doi.org/10.6084/m9.figshare.94318", "cc-by"),
    ("10.1111/j.1461-0248.2009.01305.x", "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC2886595", "unknown"),
    ("10.1086/592402", "http://www.journals.uchicago.edu/doi/pdfplus/10.1086/592402", "unknown"),
    ("10.1002/wsb.128", None, "unknown"),  # should be PD but is actually paywalled on the publisher site
    ("10.1016/0001-8708(91)90003-P", "http://doi.org/10.1016/0001-8708(91)90003-P", "unknown"),
    ("10.1038/ng.3260", "https://dash.harvard.edu/bitstream/handle/1/25290367/mallet%202015%20polytes%20commentary.preprint.pdf?sequence=1", "cc-by-nc"), # DASH example
    ("10.1021/acs.jafc.6b02480", None, "unknown"),
    ("10.1101/gad.284166.116", None, "unknown"),
    # ("10.1515/fabl.1988.29.1.21", "https://www.freidok.uni-freiburg.de/dnb/download/5273", "unknown"),  # shouldn't get urls with {{}}  keeps changing the url though so bad test
    ("10.3354/meps09890", None, "unknown"),  # has a stats.html link
    ("10.3789/isqv27no1.2015.04", "http://www.niso.org/apps/group_public/download.php/14869/NR_Breeding_Discovery_isqv27no1.pdf", "unknown"),
    ("10.1177/1525822X14564275", "https://ora.ox.ac.uk:443/objects/uuid:ccbc083c-2506-43de-a6f9-9ef621c4dece/datastreams/ATTACHMENT01", "unknown"),
    # ("10.1123/iscj.2016-0037", "http://clok.uclan.ac.uk/14950/1/Metacognition%20and%20PJDM_Author%20Accepted%20Manuscript.pdf", "unknown")  #too new, sept 2016
    ("10.1016/j.smrv.2014.11.006", "http://opus.bath.ac.uk/42098/1/insomnia_review_accepted_manuscript_1_.pdf", "unknown"),
    ("10.1038/nphoton.2015.151", "http://opus.bath.ac.uk/47347/1/NIHMS64183.pdf", "unknown"),
    ("10.1177/0892020614567246", "http://opus.bath.ac.uk/44363/1/resubmission.pdf", "unknown"),
    ("10.1111/fpa.12048", "http://opus.bath.ac.uk/42459/5/accepted_manuscript_updated_FPA.pdf", "unknown"),

]


test_urls = [
    # open from scrape tests
    ("http://doi.org/10.1002/meet.2011.14504801327", "http://onlinelibrary.wiley.com/doi/10.1002/meet.2011.14504801327/pdf", "unknown"),
    ("http://doi.org/10.1111/ele.12587", "http://onlinelibrary.wiley.com/doi/10.1111/ele.12587/pdf", "cc-by"),
    ("http://doi.org/10.1136/bmj.i2716", "http://www.bmj.com/content/bmj/353/bmj.i2716.full.pdf", "cc-by"),
    ("http://dro.dur.ac.uk/1241/", "http://dro.dur.ac.uk/1241/1/1241.pdf?DDD14+dgg1mbk+dgg0cnm", "unknown"),
    ("http://eprints.whiterose.ac.uk/77866/", "http://eprints.whiterose.ac.uk/77866/25/ggge20346_with_coversheet.pdf", "unknown"),
    ("http://hdl.handle.net/10088/17542", "https://repository.si.edu/bitstream/10088/17542/1/vz_McDade_et_al._2011_BioScience_assessment_.pdf", "unknown"),
    ("http://hdl.handle.net/1893/372", "http://dspace.stir.ac.uk/bitstream/1893/372/1/Corley%20COGNITION%202007.pdf", "unknown"),
    ("http://hdl.handle.net/2060/20140010374", "http://hdl.handle.net/2060/20140010374", "unknown"),
    ("http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6740844", "http://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=6740844", "unknown"),
    ("http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/abstract", "http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/pdf", "unknown"),
    ("http://onlinelibrary.wiley.com/doi/10.1111/tpj.12616/abstract", "http://onlinelibrary.wiley.com/doi/10.1111/tpj.12616/pdf", "unknown"),
    ("http://ro.uow.edu.au/aiimpapers/269/", "http://ro.uow.edu.au/cgi/viewcontent.cgi?article=1268&context=aiimpapers", "unknown"),
    ("http://www.emeraldinsight.com/doi/full/10.1108/00251740510597707", "http://www.emeraldinsight.com/doi/pdfplus/10.1108/00251740510597707", "unknown"),
    ("https://lirias.kuleuven.be/handle/123456789/372010", "https://lirias.kuleuven.be/handle/123456789/372010", "unknown"),
    ("https://research-repository.st-andrews.ac.uk/handle/10023/7421", "https://research-repository.st-andrews.ac.uk/bitstream/10023/7421/1/Manuscripts_edited_final.pdf", "unknown"),
    ("https://works.bepress.com/ethan_white/45/", "https://works.bepress.com/ethan_white/45/download/", "unknown"),

    # closed from scrape tests
    ("http://doi.org/10.1007/s10822-012-9571-0", None, "unknown"),
    ("http://doi.org/10.1038/nature16932", None, "unknown"),
    ("http://doi.org/10.1038/ncb3399", None, "unknown"),
    ("http://doi.org/10.1111/ele.12585", None, "unknown"),
    ("http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6045214", None, "unknown"),
    ("http://onlinelibrary.wiley.com/doi/10.1162/10881980152830079/abstract", None, "unknown"),
    ("http://www.emeraldinsight.com/doi/abs/10.1108/14777261111143545", None, "unknown"),
    ("http://www.sciencedirect.com/science/article/pii/S0147651300920050", None, "unknown"),
    ("https://works.bepress.com/ethan_white/27/", None, "unknown"),


]

nielsen_dois = [
	# ["10.1103/physreva.66.022317", "http://arxiv.org/pdf/quant-ph/0109064", "unknown"],  #FAILS
	# ["10.1016/s0375-9601(02)01803-0", "http://arxiv.org/pdf/quant-ph/0108020", "unknown"],  #FAILS
	["10.1103/physrevlett.89.247902", "http://arxiv.org/pdf/quant-ph/0207072", "unknown"],
	["10.1109/qels.2003.238205", "http://arxiv.org/pdf/quant-ph/0303038", "unknown"],
	["10.1103/physreva.68.042303", "http://arxiv.org/pdf/quant-ph/0303070", "unknown"],
	["10.1103/physreva.66.044301", "http://arxiv.org/pdf/quant-ph/0111053", "unknown"],
	["10.1088/0305-4470/34/35/324", "http://arxiv.org/pdf/quant-ph/0011063", "unknown"],
	["10.1103/physreva.78.032327", "http://arxiv.org/pdf/0808.3212", "unknown"],
	["10.1016/j.physd.2008.12.016", "http://arxiv.org/pdf/0809.0151", "unknown"],
	["10.1103/physreva.63.022114", "http://arxiv.org/pdf/quant-ph/0008073", "unknown"],
	["10.1103/physrevlett.86.5184", "http://arxiv.org/pdf/quant-ph/0011117", "unknown"],
	["10.1103/physreva.64.052309", "http://arxiv.org/pdf/quant-ph/0102043", "unknown"],
	["10.1103/physreva.65.040301", "http://arxiv.org/pdf/quant-ph/0106064", "unknown"],
	["10.1103/physreva.65.062312", "http://arxiv.org/pdf/quant-ph/0112097", "unknown"],
	["10.1103/physreva.66.032110", "http://arxiv.org/pdf/quant-ph/0202162", "unknown"],
	["10.1016/s0375-9601(02)01272-0", "http://arxiv.org/pdf/quant-ph/0205035", "unknown"],
	["10.1103/physreva.67.052301", "http://arxiv.org/pdf/quant-ph/0208077", "unknown"],
	["10.1103/physrevlett.91.210401", "http://arxiv.org/pdf/quant-ph/0303022", "unknown"],
	["10.1103/physrevlett.90.193601", "http://arxiv.org/pdf/quant-ph/0303038", "unknown"],
	["10.1103/physreva.69.012313", "http://arxiv.org/pdf/quant-ph/0307148", "unknown"],
	["10.1103/physreva.68.052311", "http://arxiv.org/pdf/quant-ph/0307190", "unknown"],
	["10.1103/physreva.69.032303", "http://arxiv.org/pdf/quant-ph/0308083", "unknown"],
	["10.1103/physreva.69.052316", "http://arxiv.org/pdf/quant-ph/0401061", "unknown"],
	["10.1103/physrevlett.93.040503", "http://arxiv.org/pdf/quant-ph/0402005", "unknown"],
	["10.1103/physreva.71.032318", "http://arxiv.org/pdf/quant-ph/0404132", "unknown"],
	["10.1103/physreva.71.052312", "http://arxiv.org/pdf/quant-ph/0405115", "unknown"],
	["10.1103/physreva.71.042323", "http://arxiv.org/pdf/quant-ph/0405134", "unknown"],
	["10.1103/physreva.71.062310", "http://arxiv.org/pdf/quant-ph/0408063", "unknown"],
	["10.1016/s0034-4877(06)80014-5", "http://arxiv.org/pdf/quant-ph/0504097", "unknown"],
	["10.1103/physreva.72.052332", "http://arxiv.org/pdf/quant-ph/0505139", "unknown"],
	["10.1103/physreva.75.064304", "http://arxiv.org/pdf/quant-ph/0506069", "unknown"],
	["10.1103/physrevlett.96.020501", "http://arxiv.org/pdf/quant-ph/0509060", "unknown"],
	["10.1103/physreva.73.052306", "http://arxiv.org/pdf/quant-ph/0601066", "unknown"],
	["10.1103/physreva.73.062323", "http://arxiv.org/pdf/quant-ph/0603160", "unknown"],
	["10.1126/science.1121541", "http://arxiv.org/pdf/quant-ph/0603161v2.pdf", "unknown"],
	["10.1103/physrevlett.97.110501", "http://arxiv.org/pdf/quant-ph/0605198", "unknown"],
	["10.1103/physreva.55.2547", "http://arxiv.org/pdf/quant-ph/9608001", "unknown"],
	["10.1080/09500349708231894", "http://arxiv.org/pdf/quant-ph/9610001", "unknown"],
	["10.1103/physreva.57.4153", "http://arxiv.org/pdf/quant-ph/9702049", "unknown"],
	["10.1103/physreva.56.2567", "http://arxiv.org/pdf/quant-ph/9704002", "unknown"],
	["10.1103/physrevlett.79.2915", "http://arxiv.org/pdf/quant-ph/9706006", "unknown"],
	["10.1109/18.850671", "http://arxiv.org/pdf/quant-ph/9809010v1.pdf", "unknown"],
	["10.1038/23891", "http://arxiv.org/pdf/quant-ph/9811020", "unknown"],
	["10.1103/physrevlett.83.436", "http://arxiv.org/pdf/quant-ph/9811053", "unknown"],
	["10.1103/physreva.61.064301", "http://arxiv.org/pdf/quant-ph/9908086", "unknown"],
	["10.1103/physreva.62.052308", "http://arxiv.org/pdf/quant-ph/9909020", "unknown"],
	["10.1103/physreva.62.012304", "http://arxiv.org/pdf/quant-ph/9910099", "unknown"],
	["10.1098/rspa.1998.0160", "http://arxiv.org/pdf/quant-ph/9706064", "unknown"],
	["10.1103/physrevlett.79.321", "http://arxiv.org/pdf/quant-ph/9703032", "unknown"],
	["10.1038/427016b", "http://www.nature.com/nature/journal/v427/n6969/pdf/427016b.pdf", "unknown"],
	["10.1038/462722a", "http://www.nature.com/nature/journal/v462/n7274/pdf/462722a.pdf", "unknown"],
	["10.1103/physreva.54.2629", "http://arxiv.org/pdf/quant-ph/9604022", "unknown"],
	# ["10.1103/physreva.68.012308", None, "unknown"],
	# ["10.1016/j.tcs.2012.12.012", "http://pm1.bu.edu/~tt/qcl/pdf/cleve__r19980905196f.pdf", "unknown"],
	["10.2277/0521635039", None, "unknown"],
	["10.1016/j.physd.2009.12.001", None, "unknown"],
	["10.1038/nphys1238", None, "unknown"],
]

nielsen_titles = [
    ["ROM-based computation: Quantum versus classical", "http://arxiv.org/pdf/quant-ph/0109016v2.pdf", "unknown"],
	["A simple proof of the strong subadditivity inequality", "http://arxiv.org/pdf/quant-ph/0408130", "unknown"],
	["A geometric approach to quantum circuit lower bounds", "http://arxiv.org/pdf/quant-ph/0502070", "unknown"],
	["The Solovay-Kitaev algorithm", "http://arxiv.org/pdf/quant-ph/0505030", "unknown"],
	["The geometry of quantum computation", "http://arxiv.org/pdf/quant-ph/0701004", "unknown"],
	["Quantum computing and polynomial equations over the finite field Z <inf>2</inf>", "http://arxiv.org/pdf/quant-ph/0408129", "unknown"],  #FAILE
	["Properties of quantum trajectories for counting measurements", None, "unknown"],
	["Majorization and the interconversion of bipartite states", None, "unknown"]]

random_dois = [u'10.1016/j.jglr.2015.05.001', u'10.1075/cilt.327.24lan', u'10.1002/chin.201114039', u'10.1134/s1070363216080144', u'10.1016/j.arthro.2006.11.015', u'10.1029/2016eo047765', u'10.1201/b12490-20', u'10.1055/s-002-22529', u'10.14325/mississippi/9781604732429.003.0008', u'10.1055/s-0034-1376792', u'10.3343/kjlm.2009.29.2.116', u'10.7312/columbia/9780231165358.003.0006', u'10.1166/jmihi.2014.1324', u'10.1164/ajrccm-conference.2012.a051', u'10.1093/acprof:oso/9780199655786.003.0034', u'10.1080/03610921003778159', u'10.3116/16091833/14/4/210/2013', u'10.1111/j.1540-8175.2006.00276.x-i4', u'10.2165/11537620-000000000-00000', u'10.1088/0029-5515/50/2/022003', u'10.1300/j097v14n01_05', u'10.1007/s10808-006-0050-z', u'10.1088/0031-9155/57/20/6497', u'10.1007/s12221-009-0394-0', u'10.1055/b-0036-133709', u'10.1101/pdb.rec083568', u'10.1049/el.2009.0879', u'10.4324/9781315638508', u'10.2210/pdb3kyc/pdb', u'10.1038/nature06293', u'10.1152/ajpregu.00337.2013', u'10.4067/s0718-00122013000100006', u'10.1016/j.abb.2006.07.009', u'10.1109/idaacs.2011.6072916', u'10.1109/ipsn.2014.6846783', u'10.1016/j.fertnstert.2014.12.119', u'10.1109/pawr.2014.6825723', u'10.1080/14328917.2015.1121317', u'10.1007/s12467-013-0057-z', u'10.1049/ic.2014.0171', u'10.1142/9789812839527_0038', u'10.1016/j.enpol.2009.01.044', u'10.1155/2012/531908', u'10.1177/1359105316656768', u'10.1177/0019464615573162', u'10.1080/10241220903462945', u'10.1001/jamainternmed.2013.13035', u'10.1002/chin.200034209', u'10.1007/978-90-368-1447-8_8', u'10.2172/957313', u'10.1109/crv.2009.44', u'10.4206/sint.tecnol.2009.v4n1-06', u'10.1201/b11634-3', u'10.1111/j.1600-0447.2011.01755.x', u'10.17509/bs_jpbsp.v13i2.290', u'10.1007/s00167-015-3697-2', u'10.1186/cc6842', u'10.1002/lt.v22.8', u'10.4314/eia.v40i3.17', u'10.1007/s10778-006-0156-2', u'10.1016/s0009-739x(07)71718-9', u'10.1016/j.compstruct.2009.11.004', u'10.1111/j.1365-277x.2006.00676.x', u'10.1007/s00284-006-0352-7', u'10.1080/19430892.2012.706175', u'10.1109/fskd.2010.5569694', u'10.2210/pdb4v5m/pdbx', u'10.5121/civej.2016.3208', u'10.1021/ja0642212', u'10.1002/9783527665709.ch15', u'10.3111/13696998.2011.595462', u'10.1097/cnj.0000000000000204', u'10.4028/www.scientific.net/amr.383-390.5729', u'10.1016/j.ab.2007.11.032', u'10.1007/s00348-009-0711-9', u'10.4018/ijea.2013070103', u'10.3811/jjmf.27.266', u'10.1016/j.bbr.2006.02.005', u'10.1080/00207543.2014.988892', u'10.18517/ijaseit.4.3.400', u'10.1016/j.na.2009.06.057', u'10.1080/02671522.2013.879335', u'10.1097/nhh.0b013e3181e3263a', u'10.1089/end.2008.9731', u'10.4275/kslis.2008.42.4.441', u'10.1111/j.1365-2230.2009.03749.x', u'10.13109/kind.2014.17.2.162', u'10.2172/970624', u'10.1653/024.096.0451', u'10.1016/j.foreco.2006.08.171', u'10.4018/978-1-61520-653-7', u'10.1080/13629395.2015.1131450', u'10.1158/1538-7445.sabcs15-s6-07', u'10.1371/journal.pntd.0002765', u'10.1007/s11701-014-0481-0', u'10.1016/j.conbuildmat.2015.05.122', u'10.1016/j.jpedsurg.2016.06.008', u'10.1007/s00134-007-0673-4', u'10.5194/amt-7-1443-2014', u'10.1186/s12889-015-2466-y']


########### ones we still get wrong

# has a different author in crossref and base
#     ("10.1056/nejmoa1509388", "http://digitalcommons.wustl.edu/cgi/viewcontent.cgi?article=5476&context=open_access_pubs", "unknown"),

# closed ones from juan that we say are open
 # '10.1016/s0140-6736(15)01156-3',
 # '10.1016/s0140-6736(16)00577-8',
 # '10.1016/s0140-6736(16)30370-1',
 # '10.1016/s0140-6736(16)30579-7',
 # '10.1038/nature16932',

# this is my nature paper, it is open on figshare
# http://doi.org/10.1038/493159a
# and listed on base https://www.base-search.net/Record/ed64a4b151d7f2fd9d68f0c81c747af73af84d2e13b77dfd9821b8980a23a9f1/

# closed JAMA from juan.  causes timeouts.
# 10.1001/jamainternmed.2016.1615
# 10.1001/jamapsychiatry.2016.2387
# 10.1001/jama.2016.4666
# 10.1001/jamaoncol.2016.0843
# 10.1001/jamaophthalmol.2016.1139

# open JAMA from juan, but timeouts and we get them wrong
# 10.1001/jama.2016.5989
# 10.1001/jamaoncol.2016.1025
# 10.1001/jama.2016.1712

# 10.1002/ecy.1605
# is available in biorxiv here 10.1101/018861 but the biorxiv version not indexed in base.
# not sure why not, have dropped base a note.

# we don't figure out the redirected pdf is actually a pdf (this one we end up getting via repo)
#    ("10.1364/boe.7.003795", "http://doi.org/10.1364/boe.7.003795", "unknown"),

# michael nielson's.  is in arxiv.
# "10.2277/0521635039"

# tell base about these
# is open at PMC.  BASE says is open but gives only a closed access url.
# so we are going to say it is closed from a scraping perspective.
# = closed 10.1038/nature16932

# this one works in api but fails in testing, maybe because of user-agent?  not sure
# ("10.1136/bjsports-2016-096194", None, "unknown"),



def guts(biblio):
    my_pub = publication.get_pub_from_biblio(biblio, force_refresh=True)
    return my_pub



@ddt
class MyTestCase(unittest.TestCase):
    _multiprocess_can_split_ = True

    @data(*test_dois)
    def test_dois(self, test_data):
        (doi, fulltext_url, license) = test_data
        biblio = {"doi": doi}
        my_product = guts(biblio)
        print u'\n\n("{}", "{}", "{}"),\n\n'.format(my_product.doi, my_product.fulltext_url, my_product.license)
        print u"\n\nwas looking for {}, got {}".format(fulltext_url, my_product.fulltext_url)
        print u"doi: {}".format(doi)
        print u"title: {}\n\n".format(my_product.best_title)
        assert_equals(my_product.fulltext_url, fulltext_url)
        assert_equals(my_product.license, license)

    @data(*test_urls)
    def test_urls(self, test_data):
        (url, fulltext_url, license) = test_data
        biblio = {"url": url}
        my_product = guts(biblio)
        print u'\n\n("{}", "{}", "{}"),\n\n'.format(my_product.url, my_product.fulltext_url, my_product.license)
        assert_equals(my_product.fulltext_url, fulltext_url)
        assert_equals(my_product.license, license)


    @data(*nielsen_dois)
    def test_neilsen_dois(self, test_data):
        (doi, fulltext_url, license) = test_data
        biblio = {"doi": doi}
        my_product = guts(biblio)
        print u"\n\nwas looking for {}, got {}".format(fulltext_url, my_product.fulltext_url)
        print u"doi: {}".format(doi)
        print u"title: {}".format(my_product.best_title)
        assert_equals(my_product.fulltext_url, fulltext_url)

    @data(*nielsen_titles)
    def test_neilsen_titles(self, test_data):
        (title, fulltext_url, license) = test_data
        biblio = {"title": title}
        my_product = guts(biblio)
        print u"\n\nwas looking for {}, got {}".format(fulltext_url, my_product.fulltext_url)
        print u"title: {}".format(title)
        assert_equals(my_product.fulltext_url, fulltext_url)



    # @data(*random_dois)
    # def test_random_dois(self, doi):
    #     biblio = {"doi": doi}
    #     my_product = guts(biblio)
    #     if my_product.fulltext_url:
    #         print doi, my_product.fulltext_url, my_product.license
    #     assert_equals(my_product.fulltext_url, None)


# class MyTestCase2(unittest.TestCase):
#     _multiprocess_can_split_ = True
#     def test_print_out(self):
#         prints = ""
#         for doi in random_dois:
#             biblio = {"url": doi}
#             my_product = guts(biblio)
#             url_string = my_product.fulltext_url
#             if url_string:
#                 url_string = u'"{}"'.format(url_string)
#             if my_product.fulltext_url:
#                 # prints += u'("{}", {}, "{}"),\n'.format(my_product.url, url_string, my_product.license)
#                 prints += u'("{}", {}, "{}"),\n'.format(my_product.evidence, url_string, my_product.license)
#         print prints
#         assert_equals(1, 2)