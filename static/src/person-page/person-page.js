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
                personResp: function($http, $rootScope, $route, Person){
                    $rootScope.setPersonIsLoading(true)
                    console.log("person is loading!", $rootScope)
                    return Person.load($route.current.params.orcid)
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
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
        }
        else if (ownsThisProfile && !Person.d.products.length) {
            $scope.profileStatus = "no_products"
        }
        else {
            $scope.profileStatus = "all_good"
        }

        $scope.settingEmail = false
        $scope.submitEmail = function(){
            var email = $scope.userForm.email
            console.log("setting the email!", email)
            $scope.settingEmail = true
            $http.post("/api/me", {email: email})
                .success(function(resp){
                    // set the email with Intercom
                    window.Intercom("update", {
                        user_id: $auth.getPayload().sub, // orcid ID
                        email: email
                    })

                    // force the person to reload
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

        $scope.d.linkTwitterLoading = false
        $scope.linkTwitter = function(){
            console.log("link twitter!")
            $scope.d.linkTwitterLoading = true
            $auth.authenticate('twitter').then(
                function(resp){
                    console.log("we linked twitter!")
                    Person.reload().then(
                        function(){
                            $scope.d.linkTwitterLoading = false
                            var confirm = $mdDialog.confirm()
                                .clickOutsideToClose(true)
                                .title("Success!")
                                .textContent("Your Impactstory profile is now linked with your Twitter account.")
                                .ok("ok")

                            $mdDialog.show(confirm).then(function(){
                                $route.reload()
                            })
                        }
                    )

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
                    // force the person to reload
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




        $scope.follow = function(){
            console.log("ya follow?")
        }







        // posts and mentions stuff
        var posts = []
        _.each(Person.d.products, function(product){
            var myDoi = product.doi
            var myTitle = product.title
            _.each(product.posts, function(myPost){
                myPost.citesDoi = myDoi
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
        console.log("genres", $scope.genres)
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



