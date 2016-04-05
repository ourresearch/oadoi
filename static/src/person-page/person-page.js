angular.module('personPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/:tab?', {
            templateUrl: 'person-page/person-page.tpl.html',
            controller: 'personPageCtrl',
            reloadOnSearch: false,
            resolve: {
                personResp: function($http, $route, Person){
                    return Person.load($route.current.params.orcid)
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           personResp){



        $scope.global.title = Person.d.given_names + " " + Person.d.family_name
        $scope.person = Person.d
        $scope.products = Person.d.products
        $scope.sources = Person.d.sources
        $scope.badges = Person.d.badges
        $scope.d = {}



        console.log("retrieved the person", $scope.person)

        $scope.profileStatus = "all_good"
        $scope.tab =  $routeParams.tab || "overview"

        //if (!Person.d.email) {
        //    $scope.userForm = {}
        //    $scope.profileStatus = "no_email"
        //}
        //else if (!Person.d.products) {
        //    $scope.profileStatus = "no_products"
        //}
        //else {
        //    $scope.profileStatus = "all_good"
        //}

        $scope.settingEmail = false
        $scope.submitEmail = function(){
            console.log("setting the email!", $scope.userForm.email)
            $scope.settingEmail = true
            $http.post("/api/me", {email: $scope.userForm.email})
                .success(function(resp){
                    $scope.settingEmail = false
                    $route.reload()
                })
        }





        $scope.badgeLimit = 3
        $scope.numBadgesToShow = 3
        $scope.toggleBadges = function(){
            if ($scope.numBadgesToShow == 3) {
                $scope.numBadgesToShow = 9999999999
            }
            else {
                $scope.numBadgesToShow = 3
            }
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
        $scope.d.postsLimit = 20

        _.each(Person.d.sources, function(v){
            $scope.postsSum += v.posts_count
        })

        $scope.selectedChannel = undefined
        $scope.toggleSelectedChannel = function(channel){
            $scope.d.postsLimit = 20
            if ($scope.selectedChannel === channel){
                $scope.selectedChannel = undefined
            }
            else {
                setSelectedChannel(channel)
            }
        }

        var setSelectedChannel = function(channel){
            $scope.selectedChannel = channel

            if ($routeParams.tab != 'mentions') {
                $location.url("u/" + Person.d.orcid_id + "/mentions?filter=" + channel)
            }
        }

        if ($routeParams.tab == "mentions"){
            if ($location.search().filter){
                var channelName = $location.search().filter
                var myChannel = _.find(Person.d.sources, function(v){
                    return v.source_name = myChannelName
                })
                setSelectedChannel(myChannel)
                $location.search({filter: null})
            }
            else {
                setSelectedChannel(undefined)
            }
        }






        // genre stuff
        var genreGroups = _.groupBy(Person.d.products, "genre")
        var genres = []
        _.each(genreGroups, function(v, k){
            genres.push({
                name: k,
                count: v.length
            })
        })
        console.log("genres", genres)

        $scope.genres = genres
        $scope.selectedGenre = undefined
        $scope.toggleSeletedGenre = function(genre){
            if ($scope.selectedGenre === genre){
                $scope.selectedGenre = undefined
            }
            else {
                $scope.selectedGenre = genre
            }            
        }



        // achievements stuff
        $scope.selectedSubscore = undefined
        $scope.toggleSeletedSubscore = function(subscore){
            console.log("toggle subscore")
            if ($scope.selectedSubscore === subscore){
                $scope.selectedSubscore = undefined
            }
            else {
                $scope.selectedSubscore = subscore
            }
        }

        // put the badge counts in each subscore
        var subscores = _.map(Person.d.subscores, function(subscore){
            var matchingBadges = _.filter(Person.d.badges, function(badge){
                return badge.group == subscore.name
            })
            subscore.badgesCount = matchingBadges.length
            return subscore
        })
        $scope.subscores = subscores





        // dialog stuff
        $scope.personScoreModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title('The online impact score')
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                //.targetEvent(ev)
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("learn more")
                $location.path("about/metrics")
            }, function() {
                console.log("ok")
            });
        };


        $scope.tIndexModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title("t-index")
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };


        $scope.impressionsModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title("Twitter impressions")
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };






    })



