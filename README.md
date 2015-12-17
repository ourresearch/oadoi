
## We need to value the software that powers science

Today's cutting-edge science is built on an array of specialist research software. This research software is often as important as traditional scholarly papers--[but it's not treated that way when it comes to funding and tenure](http://sciencecodemanifesto.org/). There, the traditional publish-or-perish, show-me-the-Impact-Factor system still rules.

We need to fix that. We need to provide meaningful incentives for the [scientist-developers](http://dirkgorissen.com/2012/03/26/the-researcher-programmer-a-new-species/) who make important research software, so that we can keep doing important, software-driven science.

## Depsy helps value research software

[Lots of things have to happen](http://rev.oxfordjournals.org/content/early/2015/07/26/reseval.rvv014.full) to support this change. Depsy is a shot at making one of those things happen: a system that tracks the impact of software in *software-native ways*.

That means not just counting up citations to a hastily-written paper *about* the software, but actual mentions of *the software itself* in the literature. It means looking how software gets reused by other software, even when it's not cited at all. And it means understanding the full complexity of software authorship, where one project can involve hundreds of contributors in multiple roles that don't map to traditional paper authorship.

## This is just the beginning

Depsy doesn't do any of these things perfectly, and it's not supposed to. Instead, Depsy is a proof-of-concept to show that we can do them at all. The data and tools are there. We *can* measure and reward software impact, like we measure and reward the impact of papers.

Given that, it's not a question of *if* research software becomes a first-class scientific product, but *when* and *how*. So let's start talking about when and how. Let's improve Depsy, let's build tools better than Depsy, and let's (most importantly) build the cultural and political structures that can use these systems.

## Let's talk details

### Coverage

Depsy tracks research software packages hosted on either [CRAN](https://cran.r-project.org/web/packages/) (the main [software repository](https://en.wikipedia.org/wiki/Software_repository) for the R programming language) or [PyPI](http://pypi.python.org) (the software repository for Python-language software). That adds up to 7,057 active R research software projects on Depsy, and 4,166 active Python research software projects.

We've found all this software being credited in the scholarly literature 83,445 times, reused by other software 960,619 times, and downloaded 221,368,685 (last month). For a better overview of all this data, plus details on how we collect and process it, check out [the paper](https://github.com/Impactstory/depsy-research/blob/master/introducing_depsy.md) in progress.


### Access to data

Everything in Depsy is open, and we encourage reuse of the data and code. You can use the API (see "View in Api" buttons on the package, person, and tag pages), or get larger-scale access via our read-only postgres database. The database connection details (plus an example of how to connect in R) are in [the Knitr source for the paper](https://github.com/Impactstory/depsy-research/blob/master/introducing_depsy.Rmd).


### Funding

Depsy is being built at [Impactstory](https://impactstory.org/about) by Jason Priem and Heather Piwowar, and is funded by an [EAGER grant](http://blog.impactstory.org/impactstory-awarded-300k-nsf-grant/) from the National Science Foundation.