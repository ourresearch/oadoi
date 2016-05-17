angular.module('personPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/:tab?/:filter?', {
            templateUrl: 'person-page/person-page.tpl.html',
            controller: 'personPageCtrl',
            reloadOnSearch: false,
            resolve: {
                personResp: function($q, $http, $rootScope, $route, $location, Person){
                    $rootScope.setPersonIsLoading(true)
                    console.log("person is loading!", $rootScope)
                    var urlId = $route.current.params.orcid

                    if (urlId.indexOf("0000-") === 0){ // got an ORCID
                        return Person.load(urlId)
                    }
                    else { // got a twitter name
                        console.log("got something other than an orcid in the slug. trying as twitter ID")
                        var deferred = $q.defer()

                        $http.get("/api/person/twitter_screen_name/" + urlId)
                            .success(function(resp){
                                console.log("this twitter name has an ORCID. redirecting there: ", resp.id)
                                // we don't reject of resolve the promise. that's
                                // to keep this route from resolving and showing garbage while
                                // the redirect is loading.
                                $location.url("/u/" + resp.id)
                            })
                            .error(function(resp){
                                console.log("got 404 resp back about the twitter name")
                                deferred.reject()
                            })
                        return deferred.promise
                    }
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
                                           $rootScope,
                                           $route,
                                           $http,
                                           $auth,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           personResp){





        $scope.global.personIsLoading = false
        $scope.global.title = Person.d.given_names + " " + Person.d.family_name
        $scope.person = Person.d
        $scope.products = Person.d.products
        $scope.sources = Person.d.sources
        $scope.badges = Person.badgesToShow()
        $scope.d = {}


        var ownsThisProfile = $auth.isAuthenticated() && $auth.getPayload().sub == Person.d.orcid_id

        $scope.ownsThisProfile = ownsThisProfile


        console.log("retrieved the person", $scope.person)

        $scope.profileStatus = "all_good"
        $scope.tab =  $routeParams.tab || "overview"
        $scope.userForm = {}

        if (ownsThisProfile && !Person.d.email ) {
            $scope.profileStatus = "no_email"
            $scope.setEmailMethod = "twitter"
        }
        else if (ownsThisProfile && !Person.d.products.length) {
            $scope.profileStatus = "no_products"
        }
        else {
            $scope.profileStatus = "all_good"
        }

        console.log("routeparamas", $routeParams)
        if ($routeParams.filter == "mendeley"){
            $scope.d.showMendeleyDetails = true
        }
        else {
            $scope.showMendeleyDetails = false
        }


        var reloadWithNewEmail = function(){
            Person.reload().then(
                function(resp){
                    window.Intercom("update", {
                        user_id: $auth.getPayload().sub, // orcid ID
                        email: Person.d.email
                    })
                    console.log("Added this person's email in Intercom. Reloading page.", Person)
                    $route.reload()
                },
                function(resp){
                    console.log("bad! Person.reload() died in finishing the profile.", resp)
                }
            )
        }

        $scope.submitEmail = function(){
            console.log("setting the email!", $scope.userForm.email)
            $rootScope.setPersonIsLoading(true)
            $scope.profileStatus = "blank"
            $http.post("/api/me", {email: $scope.userForm.email})
                .success(function(resp){
                    reloadWithNewEmail()
                })
        }

        $scope.linkTwitter = function(){
            console.log("link twitter!")
            $scope.profileStatus = "blank"
            $rootScope.setPersonIsLoading(true)

            // on the server, when we link twitter we also set the email
            $auth.authenticate('twitter').then(
                function(resp){
                    console.log("authenticate successful.", resp)
                    reloadWithNewEmail()
                },
                function(resp){
                    console.log("linking twitter didn't work!", resp)
                }
            )
        }


        $scope.pullFromOrcid = function(){
            console.log("ah, refreshing!")
            $scope.d.syncing = true
            $http.post("/api/person/" + Person.d.orcid_id)
                .success(function(resp){
                    // jason or heather might be refreshing this profile
                    // for admin/debug reasons using Secret Button.
                    // don't send event for that.
                    if (ownsThisProfile){
                        $rootScope.sendToIntercom(resp)
                        Intercom('trackEvent', 'synced');
                        Intercom('trackEvent', 'synced-to-signup');
                    }

                    // force the Person to reload. without this
                    // the newly-synced data never gets displayed.
                    console.log("reloading the Person")
                    Person.reload().then(
                        function(resp){
                            $scope.profileStatus = "all_good"
                            console.log("success, reloading page.")
                            $route.reload()
                        }
                    )
                })
        }



        $scope.shareProfile = function(){
            if (!ownsThisProfile){
                return false // just to make sure
            }
            var myOrcid = $auth.getPayload().sub // orcid ID

            console.log("sharing means caring")
            var aDayAgo = moment().subtract(24, 'hours')
            var claimedAt = moment(Person.d.claimed_at)

            // which came first: a day ago, or when this was claimed?
            if (moment.min(aDayAgo, claimedAt) == aDayAgo){
                console.log("this profile is brand spankin' new! logging it.")

                $http.post("api/person/" + myOrcid + "/tweeted-quickly", {})
                    .success(function(resp){
                        console.log("logged the tweet with our DB", resp)
                    })

                window.Intercom("update", {
                    user_id: myOrcid,
                    tweeted_quickly: true
                })
            }

        }







        // posts and mentions stuff
        var posts = []
        _.each(Person.d.products, function(product){
            var myDoi = product.doi
            var myPublicationId = product.id
            var myTitle = product.title
            _.each(product.posts, function(myPost){
                myPost.citesDoi = myDoi
                myPost.citesPublication = myPublicationId
                myPost.citesTitle = myTitle
                posts.push(myPost)
            })
        })

        function makePostsWithRollups(posts){
            var sortedPosts = _.sortBy(posts, "posted_on")
            var postsWithRollups = []
            function makeRollupPost(){
                return {
                    source: 'tweetRollup',
                    posted_on: '',
                    count: 0,
                    tweets: []
                }
            }
            var currentRollup = makeRollupPost()
            _.each(sortedPosts, function(post){
                if (post.source == 'twitter'){

                    // we keep tweets as regular posts too
                    postsWithRollups.push(post)

                    // put the tweet in the rollup
                    currentRollup.tweets.push(post)

                    // rollup posted_on date will be date of *first* tweet in group
                    if (!currentRollup.posted_on){
                        currentRollup.posted_on = post.posted_on
                    }
                }
                else {
                    postsWithRollups.push(post)

                    // save the current rollup
                    if (currentRollup.tweets.length){
                        postsWithRollups.push(currentRollup)
                    }

                    // clear the current rollup
                    currentRollup = makeRollupPost()
                }
            })

            // there may be rollup still sitting around because no regular post at end
            if (currentRollup.tweets.length){
                postsWithRollups.push(currentRollup)
            }
            return postsWithRollups
        }

        $scope.posts = makePostsWithRollups(posts)
        $scope.mendeleySource = _.findWhere(Person.d.sources, {source_name: "mendeley"})
        $scope.mostBookmarkedProducts = _.sortBy(Person.d.products, function(product){
            return product.mendeley.readers
        })

        $scope.postsFilter = function(post){
            if ($scope.selectedChannel) {
                return post.source == $scope.selectedChannel.source_name
            }
            else { // we are trying to show unfiltered view

                // but even in unfiltered view we want to hide tweets.
                return post.source != 'twitter'

            }
        }

        $scope.postsSum = 0
        _.each(Person.d.sources, function(v){
            $scope.postsSum += v.posts_count
        })

        $scope.d.viewItemsLimit = 20
        $scope.selectedChannel = _.findWhere(Person.d.sources, {source_name: $routeParams.filter})

        $scope.toggleSelectedChannel = function(channel){
            console.log("toggling selected channel", channel)
            if (channel.source_name == $routeParams.filter){
                $location.url("u/" + Person.d.orcid_id + "/mentions")
            }
            else {
                $location.url("u/" + Person.d.orcid_id + "/mentions/" + channel.source_name)
            }
        }










        // genre stuff
        var genreGroups = _.groupBy(Person.d.products, "genre")
        var genres = []
        _.each(genreGroups, function(v, k){
            genres.push({
                name: k,
                display_name: k.split("-").join(" "),
                count: v.length
            })
        })

        $scope.genres = genres
        $scope.selectedGenre = _.findWhere(genres, {name: $routeParams.filter})
        $scope.toggleSeletedGenre = function(genre){
            if (genre.name == $routeParams.filter){
                $location.url("u/" + Person.d.orcid_id + "/publications")
            }
            else {
                $location.url("u/" + Person.d.orcid_id + "/publications/" + genre.name)
            }
        }











        // achievements stuff
        var subscoreSortOrder = {
            buzz: 1,
            engagement: 2,
            openness: 3,
            fun: 4
        }
        
        // put the badge counts in each subscore
        var subscores = _.map(Person.d.subscores, function(subscore){
            var matchingBadges = _.filter(Person.badgesToShow(), function(badge){
                return badge.group == subscore.name
            })
            subscore.badgesCount = matchingBadges.length
            subscore.sortOrder = subscoreSortOrder[subscore.name]
            return subscore
        })
        $scope.subscores = subscores
        $scope.selectedSubscore = _.findWhere(subscores, {name: $routeParams.filter})

        $scope.toggleSeletedSubscore = function(subscore){
            console.log("toggle subscore", subscore)
            if (subscore.name == $routeParams.filter){
                $location.url("u/" + Person.d.orcid_id + "/achievements")
            }
            else {
                $location.url("u/" + Person.d.orcid_id + "/achievements/" + subscore.name)
            }
        }









    })



