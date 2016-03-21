#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import re

# from http://www.sciencemag.org/news/2014/09/top-50-science-stars-twitter
scientists_string = """1. Neil deGrasse Tyson, Astrophysicist
2,400,000 followers @neiltyson
Citations: 151 K-index: 11129
Total number of tweets: 3,962
Hayden Planetarium, United States
Brian Cox
2. Brian Cox, Physicist
1,440,000 followers @ProfBrianCox
Citations: 33,301 K-index: 1188
Total number of tweets: 10,300
University of Manchester, United Kingdom
Richard Dawkins
3. Richard Dawkins, Biologist
1,020,000 followers @RichardDawkins
Citations: 49,631 K-index: 740
Total number of tweets: 19,000
University of Oxford, United Kingdom
Ben Goldacre
4. Ben Goldacre, Physician
341,000 followers @bengoldacre
Citations: 1,086 K-index: 841
Total number of tweets: 47,300
London School of Hygiene & Tropical Medicine, United Kingdom
Phil Plait
5. Phil Plait, Astronomer
320,000 followers @BadAstronomer
Citations: 254 K-index: 1256
Total number of tweets: 47,000
Bad Astronomy, United States
Michio Kaku
6. Michio Kaku, Theoretical physicist
310,000 followers @michiokaku
Citations: 5,281 K-index: 461
Total number of tweets: 1,130
The City College of New York, United States
Sam Harris
7. Sam Harris, Neuroscientist
224,000 followers @SamHarrisOrg
Citations: 2,416 K-index: 428
Total number of tweets: 2,600
Project Reason, United States
Hans Rosling
8. Hans Rosling, Global health scientist
180,000 followers @HansRosling
Citations: 1,703 K-index: 384
Total number of tweets: 2,708
Karolinska Institute, Sweden
Tim Berners-Lee
9. Tim Berners-Lee, Computer scientist
179,000 followers @timberners_lee
Citations: 51,204 K-index: 129
Total number of tweets: 542
Massachusetts Institute of Technology, United States
P.Z. Myers
10. P.Z. Myers, Biologist
155,000 followers @pzmyers
Citations: 1,364 K-index: 355
Total number of tweets: 25,400
University of Minnesota, Morris, United States
Steven Pinker
11. Steven Pinker, Cognitive scientist
142,000 followers @sapinker
Citations: 49,933 K-index: 103
Total number of tweets: 1,612
Harvard University, United States
Richard Wiseman
12. Richard Wiseman, Psychologist
134,000 followers @RichardWiseman
Citations: 4,687 K-index: 207
Total number of tweets: 22,400
University of Hertfordshire, United Kingdom
Lawrence M. Krauss
13. Lawrence M. Krauss, Theoretical physicist
99,700 followers @LKrauss1
Citations: 10,155 K-index: 120
Total number of tweets: 1,548
Arizona State University, United States
Atul Gawande
14. Atul Gawande, Surgeon/public health scientist
96,800 followers @Atul_Gawande
Citations: 13,763 K-index: 106
Total number of tweets: 2,118
Harvard University, United States
Oliver Sacks
15. Oliver Sacks, Neurologist
76,300 followers @OliverSacks
Citations: 13,883 K-index: 83
Total number of tweets: 746
New York University, United States
Dan Ariely*
16. Dan Ariely*, Psychologist/behavioral economist
73,000 followers @danariely
Citations: 16,307 K-index: 76
Total number of tweets: 1,091
Duke University, United States
Eric Topol*
17. Eric Topol*, Geneticist
44,800 followers @EricTopol
Citations: 151,281 K-index: 23
Total number of tweets: 4,966
The Scripps Research Institute, United States
Brian Greene
18. Brian Greene, Theoretical physicist
38,700 followers @bgreene
Citations: 11,133 K-index: 45
Total number of tweets: 191
Columbia University, United States
Marcus du Sautoy
19. Marcus du Sautoy, Mathematician
34,200 followers @MarcusduSautoy
Citations: 1,461 K-index: 77
Total number of tweets: 3,555
University of Oxford, United Kingdom
Sean Carroll
20. Sean Carroll, Theoretical physicist
33,200 followers @seanmcarroll
Citations: 14,208 K-index: 36
Total number of tweets: 7,295
California Institute of Technology, United States
Robert Winston
21. Robert Winston, Fertility scientist
31,900 followers @ProfRWinston
Citations: 7,324 K-index: 43
Total number of tweets: 445
Imperial College London, United Kingdom
Bruce Betts
22. Bruce Betts, Planetary scientist
28,500 followers @RandomSpaceFact
Citations: 91 K-index: 155
Total number of tweets: 1,619
The Planetary Society, United States
Carolyn Porco
23. Carolyn Porco, Planetary scientist
26,100 followers @carolynporco
Citations: 2,717 K-index: 48
Total number of tweets: 12,700
Space Science Institute, United States
Sebastian Thrun+
24. Sebastian Thrun+, Computer scientist
25,200 followers @SebastianThrun
Citations: 57,110 K-index: 17
Total number of tweets: 185
Stanford University, United States
Jonathan Eisen*
25. Jonathan Eisen*, Biologist
24,900 followers @phylogenomics
Citations: 41,289 K-index: 19
Total number of tweets: 46,100
University of California, Davis, United States
J. Craig Venter
26. J. Craig Venter, Genomicist
23,500 followers @JCVenter
Citations: 75,338 K-index: 15
Total number of tweets: 365
J. Craig Venter Institute, United States
Vaughan Bell
27. Vaughan Bell, Neuroscientist
23,500 followers @vaughanbell
Citations: 821 K-index: 63
Total number of tweets: 10,900
King's College London, United Kingdom
Robert Simpson
28. Robert Simpson, Astronomer
21,500 followers @orbitingfrog
Citations: 2,280 K-index: 42
Total number of tweets: 11,500
University of Oxford, United Kingdom
Michael E. Mann*
29. Michael E. Mann*, Meteorologist
20,900 followers @MichaelEMann
Citations: 15,049 K-index: 22
Total number of tweets: 20,000
Pennsylvania State University, United States
Jerry Coyne
30. Jerry Coyne, Biologist
19,500 followers @Evolutionistrue
Citations: 16,657 K-index: 20
Total number of tweets: 7,711
University of Chicago, United States
Gary King*
31. Gary King*, Statistician
19,400 followers @kinggary
Citations: 36,311 K-index: 16
Total number of tweets: 3,080
Harvard University, United States
Mike Brown
32. Mike Brown, Astronomer
18,300 followers @plutokiller
Citations: 7,870 K-index: 24
Total number of tweets: 9,764
California Institute of Technology, United States
Pamela L. Gay
33. Pamela L. Gay, Astronomer
17,800 followers @starstryder
Citations: 238 K-index: 71
Total number of tweets: 12,700
Southern Illinois University, Edwardsville, United States
Jean Francois Gariépy
34. Jean Francois Gariépy, Neuroscientist
17,700 followers @JFGariepy
Citations: 153 K-index: 82
Total number of tweets: 3,231
Duke University, United States
Bob Metcalfe
35. Bob Metcalfe, Computer scientist
16,400 followers @BobMetcalfe
Citations: 424 K-index: 55
Total number of tweets: 16,100
University of Texas, Austin, United States
Daniel Gilbert+
36. Daniel Gilbert+, Psychologist
15,500 followers @DanTGilbert
Citations: 26,752 K-index: 14
Total number of tweets: 1,294
Harvard University, United States
Daniel Levitin
37. Daniel Levitin, Neuroscientist
15,400 followers @danlevitin
Citations: 5,688 K-index: 22
Total number of tweets: 3,036
McGill University, Canada
Andrew Maynard
38. Andrew Maynard, Environmental health scientist
15,300 followers @2020science
Citations: 10,411 K-index: 18
Total number of tweets: 16,200
University of Michigan Risk Science Center, United States
Paul Bloom
39. Paul Bloom, Psychologist
15,100 followers @paulbloomatyale
Citations: 14,135 K-index: 16
Total number of tweets: 1,973
Yale University, United States
Matt Lieberman
40. Matt Lieberman, Neuroscientist
14,500 followers @social_brains
Citations: 12,763 K-index: 16
Total number of tweets: 3,088
University of California, Los Angeles, United States
Seth Shostak
41. Seth Shostak, Astronomer
14,500 followers @SethShostak
Citations: 424 K-index: 48
Total number of tweets: 294
SETI Institute, United States
Daniel MacArthur
42. Daniel MacArthur, Genomicist
14,100 followers @dgmacarthur
Citations: 6,884 K-index: 19
Total number of tweets: 15,600
Harvard Medical School, United States
John Allen Paulos
43. John Allen Paulos, Mathematician
14,000 followers @JohnAllenPaulos
Citations: 1,489 K-index: 31
Total number of tweets: 4,144
Temple University, United States
Ves Dimov
44. Ves Dimov, Immunologist
13,900 followers @DrVes
Citations: 211 K-index: 58
Total number of tweets: 32,200
University of Chicago, United States
Simon Baron-Cohen
45. Simon Baron-Cohen, Psychopathologist
13,600 followers @sbaroncohen
Citations: 84,132 K-index: 8
Total number of tweets: 119
University of Cambridge, United Kingdom
Amy Mainzer
46. Amy Mainzer, Astronomer
13,600 followers @AmyMainzer
Citations: 1,444 K-index: 31
Total number of tweets: 2,221
Jet Propulsion Laboratory, United States
Brian Krueger
47. Brian Krueger, Genomicist
12,500 followers @LabSpaces
Citations: 154 K-index: 58
Total number of tweets: 36,700
Duke University, United States
Karen James
48. Karen James, Biologist
12,200 followers @kejames
Citations: 1,007 K-index: 31
Total number of tweets: 61,800
Mount Desert Island Biological Laboratory, United States
Michael Eisen
49. Michael Eisen, Biologist
11,800 followers @mbeisen
Citations: 68,785 K-index: 8
Total number of tweets: 16300
University of California, Berkeley, United States
Micah Allen
50. Micah Allen, Neuroscientist
11,600 followers @neuroconscience
Citations: 81 K-index: 66
Total number of tweets: 21,900
University College London, United Kingdom"""

scientists_twitter = re.findall("@(.*)", scientists_string)