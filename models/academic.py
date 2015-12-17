

def is_academic_project(package_obj):

    is_academic = False

    # if your intended audience is scientists, you're academic
    if package_obj.intended_audience == "Science/Research":
        is_academic = True

    # if you have an academic-sounding tag, you're academic
    for tag in package_obj.tags:
        if is_academic_phrase(tag):
            is_academic = True

    # if you have an academic-sounding name, you're academic
    if is_academic_phrase(package_obj.project_name):
        is_academic = True

    # if you have an academic-sounding summary, you're academic
    if is_academic_phrase(package_obj.summary):
        is_academic = True

    return is_academic



def is_academic_phrase(phrase):
    if not phrase:
        return False

    # if you have academic-sounding tags, you're academic
    sciency_words = [
        "chemi",  
        "scien", 
        "bio",  
        "econo", 
        "omics",
        "sociology",
        "physics", 
        "psych", 
        "math", 
        "ecolog", 
        "genetics",
        "department",
        "university",
        "formatics",
        "evolution",

        "professor",
        "doctoral", 
        "phd", 
        "postdoc", 
        "post-doc",

        "astronomy",
        "astronomical",
        "astropy",
        "astrophysical",      

        "fits image",      
        "single dish otf",      
        "position-velocity diagram",      
        "montage mosaicking",    
        "monte-carlo radiative transfer",  
        "spectral cube",  
        "spectroscop",  
        "ecodata",  
        "power-law distribution",  
        "dust emissivity",  
        "interstellar",  
        "mcmc sampling",
        "gaussian process",

        # names of specific libraries; 
        # these libraries are research software, but their tags and summary don't have any words
        # which make that clear, and they don't have Science as an intended audience alas.
        # specifying them here explicitly for now till we come up with a better way.
        "astroquery",
        "pyradex"


        # tried but too many bad hits
        # "statistics",
        # "analysis", 
        # "astro"

        # not using cran tags to decide if research; decided to call all cran research
        # "chemphys",  #cran tag         
        # "experimentaldesign", 
        # "clinicaltrials", 
        # "research", 
        # "medicalimaging", 
        # "differentialequations", 
        # "pharmacokinetics", 
        # "environmetrics" 
    ]

    phrase_lower = phrase.lower()
    for sciency_word in sciency_words:
        if sciency_word in phrase_lower:
            return True

    return False


# query to test new additions
    # select id, summary, tags, is_academic from package 
    # where host='pypi'
    # and (summary ilike '%astro%'
    # or tags::text ilike '%astro%'
    # or project_name ilike '%astro%')
    # and is_academic=false